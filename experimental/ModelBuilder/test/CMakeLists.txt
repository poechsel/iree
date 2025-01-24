# Copyright 2020 Google LLC
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

iree_add_all_subdirs()

file(GLOB _GLOB_X_CPP LIST_DIRECTORIES false RELATIVE ${CMAKE_CURRENT_SOURCE_DIR} CONFIGURE_DEPENDS *.cpp)
file(GLOB _GLOB_BENCHX LIST_DIRECTORIES false RELATIVE ${CMAKE_CURRENT_SOURCE_DIR} CONFIGURE_DEPENDS Bench*)
list(REMOVE_ITEM _GLOB_X_CPP ${_GLOB_BENCHX})
iree_lit_test_suite(
  NAME
    lit
  SRCS
    "${_GLOB_X_CPP}"
  DATA
    test-dot-prod
    test-matmul-vulkan
    test-mnist-jit
    test-simple-jit
    test-simple-jit-vulkan
    test-simple-mlir
    test-vec-to-gpu
    test-vector-transfers-jit
    iree::tools::IreeFileCheck
)

iree_cc_binary(
  NAME
    test-dot-prod
  OUT
    test-dot-prod
  SRCS
    "TestDotProdJIT.cpp"
  DEPS
    LLVMSupport
    MLIRAllDialects
    MLIREDSC
    MLIRIR
    MLIRSCFTransforms
    experimental::ModelBuilder
    experimental::ModelBuilder::ModelRunner
)

iree_cc_binary(
  NAME
    test-vector-transfers-jit
  OUT
    test-vector-transfers-jit
  SRCS
    "TestVectorTransfersJIT.cpp"
  DEPS
    runtime-support.so
    LLVMSupport
    MLIRAllDialects
    MLIREDSC
    MLIRIR
    MLIRSCFTransforms
    experimental::ModelBuilder
    experimental::ModelBuilder::ModelRunner
)

iree_cc_binary(
  NAME
    test-mnist-jit
  OUT
    test-mnist-jit
  SRCS
    "TestMNISTJIT.cpp"
  DEPS
    MLIRAllDialects
    MLIREDSC
    MLIRIR
    MLIRSCFTransforms
    MLIRmlir_runner_utils
    experimental::ModelBuilder
    experimental::ModelBuilder::ModelRunner
)

iree_cc_binary(
  NAME
    test-simple-jit
  OUT
    test-simple-jit
  SRCS
    "TestSimpleJIT.cpp"
  DEPS
    LLVMSupport
    MLIRAllDialects
    MLIREDSC
    MLIRIR
    MLIRSCFTransforms
    experimental::ModelBuilder
    experimental::ModelBuilder::ModelRunner
)

iree_cc_binary(
  NAME
    test-simple-jit-vulkan
  OUT
    test-simple-jit-vulkan
  SRCS
    "TestSimpleJITVulkan.cpp"
  DEPS
    LLVMSupport
    MLIRAllDialects
    MLIRIR
    MLIRParser
    MLIRSPIRV
    MLIRmlir_runner_utils
    experimental::ModelBuilder
    experimental::ModelBuilder::ModelRunner
    iree::base::initializer
    iree::hal::llvmjit::llvmjit_driver_module
    iree::hal::vmla::vmla_driver_module
    iree::hal::vulkan::vulkan_driver_module
    vulkan-runtime-wrappers
)

iree_cc_binary(
  NAME
    test-matmul-vulkan
  OUT
    test-matmul-vulkan
  SRCS
    "TestMatMulVulkan.cpp"
  DEPS
    LLVMSupport
    MLIRAllDialects
    MLIRExecutionEngine
    MLIRGPU
    MLIRGPUToSPIRVTransforms
    MLIRGPUToVulkanTransforms
    MLIRIR
    MLIRLinalgOps
    MLIRLinalgToLLVM
    MLIRLinalgTransforms
    MLIRParser
    MLIRPass
    MLIRSPIRV
    MLIRStandardToLLVM
    MLIRStandardToSPIRVTransforms
    MLIRSupport
    MLIRTargetLLVMIR
    MLIRTransformUtils
    MLIRVectorToLLVM
    MLIRmlir_runner_utils
    experimental::ModelBuilder
    experimental::ModelBuilder::ModelRunner
    experimental::ModelBuilder::VulkanLaunchWrapper
    iree::base::initializer
    iree::compiler::Conversion::LinalgToSPIRV
    iree::hal::llvmjit::llvmjit_driver_module
    iree::hal::vmla::vmla_driver_module
    iree::hal::vulkan::vulkan_driver_module
    vulkan-runtime-wrappers
)

iree_cc_binary(
  NAME
    test-vec-to-gpu
  OUT
    test-vec-to-gpu
  SRCS
    "TestVectorToGPU.cpp"
  DEPS
    LLVMSupport
    MLIRAllDialects
    MLIRExecutionEngine
    MLIRGPU
    MLIRGPUToVulkanTransforms
    MLIRIR
    MLIRLinalgOps
    MLIRLinalgToLLVM
    MLIRLinalgTransforms
    MLIRParser
    MLIRPass
    MLIRSPIRV
    MLIRStandardToLLVM
    MLIRStandardToSPIRVTransforms
    MLIRTransformUtils
    MLIRVector
    MLIRmlir_runner_utils
    experimental::ModelBuilder
    experimental::ModelBuilder::ModelRunner
    experimental::ModelBuilder::VulkanLaunchWrapper
    iree::base::initializer
    iree::compiler::Conversion::CodegenUtils
    iree::compiler::Conversion::LinalgToSPIRV
    iree::hal::llvmjit::llvmjit_driver_module
    iree::hal::vmla::vmla_driver_module
    iree::hal::vulkan::vulkan_driver_module
    vulkan-runtime-wrappers
)

iree_cc_binary(
  NAME
    test-simple-mlir
  OUT
    test-simple-mlir
  SRCS
    "TestSimpleMLIR.cpp"
  DEPS
    MLIRAllDialects
    experimental::ModelBuilder
    experimental::ModelBuilder::ModelRunner
)

iree_cc_binary(
  NAME
    bench-matvec-vector-jit
  OUT
    bench-matvec-vector-jit
  SRCS
    "BenchMatVecVectorJIT.cpp"
  DEPS
    MLIRAllDialects
    MLIREDSC
    MLIRIR
    benchmark
    experimental::ModelBuilder
    experimental::ModelBuilder::ModelRunner
)

iree_cc_binary(
  NAME
    bench-matmul-vector-jit
  OUT
    bench-matmul-vector-jit
  SRCS
    "BenchMatMulVectorJIT.cpp"
  DEPS
    MLIRAllDialects
    MLIREDSC
    MLIRIR
    benchmark
    experimental::ModelBuilder
    experimental::ModelBuilder::ModelRunner
)

iree_cc_binary(
  NAME
    bench-matmul-vector-column-major-llvm-intrinsics-jit
  OUT
    bench-matmul-vector-column-major-llvm-intrinsics-jit
  SRCS
    "BenchMatMulVectorColumnMajorLLVMIntrinsicsJIT.cpp"
  DEPS
    MLIRAllDialects
    MLIREDSC
    MLIRIR
    benchmark
    experimental::ModelBuilder
    experimental::ModelBuilder::ModelRunner
)

# TODO(thomasraoux): Fix bazel_to_cmake tto support shared library
iree_cc_library(
NAME
    runtime-support.so
  OUT
    runtime-support.so
  DEPS
    MLIRExecutionEngine
  SHARED
)
