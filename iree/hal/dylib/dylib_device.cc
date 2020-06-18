// Copyright 2020 Google LLC
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      https://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

#include "iree/hal/dylib/dylib_device.h"

#include <utility>

#include "iree/base/tracing.h"
#include "iree/hal/dylib/dylib_executable_cache.h"

namespace iree {
namespace hal {
namespace dylib {

DyLibDevice::DyLibDevice(DeviceInfo device_info,
                         std::unique_ptr<SchedulingModel> scheduling_model)
    : HostLocalDevice(std::move(device_info), std::move(scheduling_model)) {}

DyLibDevice::~DyLibDevice() = default;

ref_ptr<ExecutableCache> DyLibDevice::CreateExecutableCache() {
  IREE_TRACE_SCOPE0("DyLibDevice::CreateExecutableCache");
  return make_ref<DyLibExecutableCache>();
}

}  // namespace dylib
}  // namespace hal
}  // namespace iree