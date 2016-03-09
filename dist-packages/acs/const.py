import sys

class ConstError(TypeError):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr("Cannot rebind const %s" % self.value)
class _const:
    def __setattr__(self, name, value):
        if self.__dict__.has_key(name):
            raise self.ConstError(name)

        self.__dict__[name] = value
