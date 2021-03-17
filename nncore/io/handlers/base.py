# Copyright (c) Ye Liu. All rights reserved.

from abc import ABCMeta, abstractmethod


class FileHandler(metaclass=ABCMeta):

    @abstractmethod
    def load_from_file(self):
        pass

    @abstractmethod
    def dump_to_file(self):
        pass

    def load_from_str(self):
        raise NotImplementedError

    def dump_to_str(self):
        raise NotImplementedError

    def load_from_path(self, file, mode='r', **kwargs):
        with open(file, mode) as f:
            return self.load_from_file(f, **kwargs)

    def dump_to_path(self, obj, file, mode='w', **kwargs):
        with open(file, mode) as f:
            self.dump_to_file(obj, f, **kwargs)
