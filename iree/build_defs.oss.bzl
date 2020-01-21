# Copyright 2019 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Common Bazel definitions for IREE."""

load("@com_github_google_flatbuffers//:build_defs.bzl", "flatbuffer_cc_library")
load("@rules_cc//cc:defs.bzl", _cc_binary = "cc_binary", _cc_library = "cc_library")
load("@iree_core//build_tools/third_party/glslang:build_defs.bzl", "glsl_vulkan")
load("@iree_core//iree:lit_test.bzl", _iree_glob_lit_tests = "iree_glob_lit_tests", _iree_setup_lit_package = "iree_setup_lit_package")

# Target to the FileCheck binary.
INTREE_FILECHECK_TARGET = "@llvm-project//llvm:FileCheck"

def iree_setup_lit_package(**kwargs):
    _iree_setup_lit_package(**kwargs)

def iree_glob_lit_tests(**kwargs):
    _iree_glob_lit_tests(**kwargs)

def platform_trampoline_deps(basename, path = "base"):
    """Produce a list of deps for the given `basename` platform target.

    Example:
      "file_mapping" -> ["//iree/base/internal/file_mapping_internal"]

    This is used for compatibility with various methods of including the
    library in foreign source control systems.

    Args:
      basename: Library name prefix for a library in iree/[path]/internal.
      path: Folder name to work within.
    Returns:
      A list of dependencies for depending on the library in a platform
      sensitive way.
    """
    return [
        "//iree/%s/internal:%s_internal" % (path, basename),
    ]

# A platform-sensitive list of copts for the Vulkan loader.
PLATFORM_VULKAN_LOADER_COPTS = select({
    "//iree/hal/vulkan:native_vk": [],
    "//iree/hal/vulkan:swiftshader_vk": [],
    "//conditions:default": [],
})

# A platform-sensitive list of dependencies for non-test targets using Vulkan.
PLATFORM_VULKAN_DEPS = select({
    "//iree/hal/vulkan:native_vk": [],
    "//iree/hal/vulkan:swiftshader_vk": [],
    "//conditions:default": [],
})

# A platform-sensitive list of dependencies for tests using Vulkan.
PLATFORM_VULKAN_TEST_DEPS = [
    "//iree/testing:gtest_main",
]

# Aliases to the Starlark cc rules.
cc_library = _cc_library
cc_binary = _cc_binary

def iree_build_test(name, targets):
    """Dummy rule to ensure that targets build.

    This is currently undefined in bazel and is preserved for compatibility.
    """
    pass

# The OSS build currently has issues with generating flatbuffer reflections.
# It is hard-coded to disabled here (and in iree_flatbuffer_cc_library) until triaged/fixed.
FLATBUFFER_SUPPORTS_REFLECTIONS = False

def iree_flatbuffer_cc_library(**kwargs):
    """Wrapper for the flatbuffer_cc_library."""

    # TODO(laurenzo): The bazel rule for reflections seems broken in OSS
    # builds. Fix it and enable by default.
    flatbuffer_cc_library(
        gen_reflections = False,
        **kwargs
    )

def iree_glsl_vulkan(**kwargs):
    glsl_vulkan(**kwargs)