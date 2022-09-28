from typing import Union
from dbacademy_gems import dbgems


class Paths:

    def __init__(self, working_dir_root: str, working_dir: str, datasets: str, user_db: Union[str, None], enable_streaming_support: bool):

        self.datasets = datasets
        self.user_db = user_db
        self.working_dir = working_dir

        self._working_dir_root = working_dir_root

        # When working with streams, it helps to put all checkpoints in their
        # own directory relative the previously defined working_dir
        if enable_streaming_support:
            self.checkpoints = f"{working_dir}/_checkpoints"

    # noinspection PyGlobalUndefined
    @staticmethod
    def exists(path):
        global dbutils

        """
        Returns true if the specified path exists else false.
        """
        try:
            return len(dbgems.dbutils.fs.ls(path)) >= 0
        except Exception:
            return False

    def print(self, padding="  ", self_name="self."):
        """
        Prints all the paths attached to this instance of Paths
        """
        max_key_len = 0
        for key in self.__dict__:
            if not key.startswith("_"):
                max_key_len = len(key) if len(key) > max_key_len else max_key_len

        for key in self.__dict__:
            if not key.startswith("_"):
                label = f"{padding}{self_name}paths.{key}: "
                print(label.ljust(max_key_len + 13) + self.__dict__[key])

    def __repr__(self):
        return self.__dict__.__repr__().replace(", ", ",\n").replace("{", "").replace("}", "").replace("'", "")