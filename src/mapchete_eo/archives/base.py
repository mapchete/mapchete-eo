class Archive:
    @property
    def fs_storage_options(self):
        raise NotImplementedError()

    @property
    def rio_env_options(self):
        raise NotImplementedError()
