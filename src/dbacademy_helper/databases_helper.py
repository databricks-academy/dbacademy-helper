from dbacademy_gems import dbgems
from dbacademy_helper import DBAcademyHelper
from dbacademy_helper.workspace_helper import WorkspaceHelper
from typing import Callable, TypeVar
T=TypeVar("T")

class DatabasesHelper:
    def __init__(self, workspace: WorkspaceHelper, da: DBAcademyHelper):
        self.da = da
        self.client = da.client
        self.workspace = workspace

    def drop_databases(self):
        self.workspace.do_for_all_users(lambda username: self._drop_databases_for(username=username))

        # Clear the list of databases (and derived users) to force a refresh
        self.workspace._usernames = None
        self.workspace._existing_databases = None

    def _drop_databases_for(self, username: str):
        db_name = self.da.to_database_name(username=username, course_code=self.da.course_code)
        if db_name in self.workspace.existing_databases:
            print(f"Dropping the database \"{db_name}\" for {username}")
            dbgems.get_spark_session().sql(f"DROP DATABASE {db_name} CASCADE;")
        else:
            print(f"Skipping database drop for {username}")

    def create_databases(self, drop_existing: bool, post_create: Callable[[], None] = None):
        self.workspace.do_for_all_users(lambda username: self._create_database_for(username=username,
                                                                                  drop_existing=drop_existing,
                                                                                  post_create=post_create))
        # Clear the list of databases (and derived users) to force a refresh
        self.workspace._usernames = None
        self.workspace._existing_databases = None

    def _create_database_for(self, username: str, drop_existing: bool, post_create: Callable[[str], None] = None):
        db_name = self.da.to_database_name(username=username, course_code=self.da.course_code)
        db_path = f"dbfs:/mnt/dbacademy-users/{username}/{self.da.course_name}/database.db"

        if db_name in self.da.workspace.existing_databases and drop_existing:
            print(f"Dropping the database \"{db_name}\" for {username}")
            dbgems.get_spark_session().sql(f"DROP DATABASE {db_name} CASCADE;")

        print(f"Creating database \"{db_name}\" for {username}")
        dbgems.get_spark_session().sql(f"CREATE DATABASE IF NOT EXISTS {db_name} LOCATION '{db_path}';")

        if post_create:
            # Call the post-create init function if defined
            post_create(db_name)

        return f"Created database {db_name}"

    def configure_permissions(self, notebook_name="Configure-Permissions"):

        job_name = f"DA-{self.da.course_code}-{notebook_name}"
        print(f"Starting job \"{job_name}\" to catalog and schema specific permissions")

        self.client.jobs().delete_by_name(job_name, success_only=False)

        notebook_path = f"{dbgems.get_notebook_dir()}/{notebook_name}"

        params = {
            "name": job_name,
            "tags": {
                "dbacademy.course": self.da.clean_string(self.da.course_name),
                "dbacademy.source": self.da.clean_string("Smoke-Test" if self.da.is_smoke_test() else self.da.course_name)
            },
            "email_notifications": {},
            "timeout_seconds": 7200,
            "max_concurrent_runs": 1,
            "format": "MULTI_TASK",
            "tasks": [
                {
                    "task_key": "Configure-Permissions",
                    "description": "Configure all users's permissions for user-specific databases.",
                    "libraries": [],
                    "notebook_task": {
                        "notebook_path": notebook_path,
                        "base_parameters": {
                            "configure_for": self.workspace.configure_for
                        }
                    },
                    "new_cluster": {
                        "num_workers": "0",
                        "spark_conf": {
                            "spark.master": "local[*]",
                            "spark.databricks.acl.dfAclsEnabled": "true",
                            "spark.databricks.repl.allowedLanguages": "sql,python",
                            "spark.databricks.cluster.profile": "serverless",
                        },
                        "runtime_engine": "STANDARD",
                    },
                },
            ],
        }
        cluster_params = params.get("tasks")[0].get("new_cluster") # Photon currently is not supported on these cluster types
        cluster_params["spark_version"] = self.client.clusters().get_current_spark_version().replace("-photon-", "-")

        if self.client.clusters().get_current_instance_pool_id() is not None:
            cluster_params["instance_pool_id"] = self.client.clusters().get_current_instance_pool_id()
        else:
            cluster_params["node_type_id"] = self.client.clusters().get_current_node_type_id()
            if dbgems.get_cloud() == "AWS":
                cluster_params["aws_attributes"] = {"availability": "ON_DEMAND"}

        create_response = self.client.jobs().create(params)
        job_id = create_response.get("job_id")

        run_response = self.client.jobs().run_now(job_id)
        run_id = run_response.get("run_id")

        final_response = self.client.runs().wait_for(run_id)

        final_state = final_response.get("state").get("result_state")
        assert final_state == "SUCCESS", f"Expected the final state to be SUCCESS, found {final_state}"

        print()
        print("Update completed successfully.")
        return job_name
