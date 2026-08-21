"""Small py2app compatibility fixes used only while building the macOS app."""

from functools import wraps

_PATCH_FLAG = "_yt_transcript_builtin_zlib_patch"
_BUILTIN_ZLIB_MARKER = "__py2app_builtin_zlib__"


def patch_py2app_for_builtin_zlib(py2app_command, zlib_module) -> bool:
    """Skip py2app's file copy when zlib is built into the Python executable.

    Python distributions installed by uv can compile zlib as a built-in module,
    which correctly has no ``__file__``. py2app 0.28.10 assumes that every zlib
    module is a shared library and otherwise crashes while creating the bundle.
    """
    if getattr(zlib_module, "__file__", None):
        return False
    if getattr(py2app_command, _PATCH_FLAG, False):
        return False

    original_build_executable = py2app_command.build_executable

    @wraps(original_build_executable)
    def build_executable(self, *args, **kwargs):
        original_copy_file = self.copy_file
        missing = object()
        previous_instance_copy_file = vars(self).get("copy_file", missing)

        def copy_file(source, destination, *copy_args, **copy_kwargs):
            if source == _BUILTIN_ZLIB_MARKER:
                return destination, False
            return original_copy_file(source, destination, *copy_args, **copy_kwargs)

        zlib_module.__file__ = _BUILTIN_ZLIB_MARKER
        self.copy_file = copy_file
        try:
            return original_build_executable(self, *args, **kwargs)
        finally:
            if previous_instance_copy_file is missing:
                del self.copy_file
            else:
                self.copy_file = previous_instance_copy_file
            del zlib_module.__file__

    py2app_command.build_executable = build_executable
    setattr(py2app_command, _PATCH_FLAG, True)
    return True
