# Lint as: python3
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
"""Test utilities interop with TensorFlow."""

# pylint: disable=not-callable
# pylint: disable=invalid-name
# pylint: disable=missing-docstring
# pylint: disable=protected-access

import collections
import os
import random
import re
import tempfile

from absl import flags
from absl import logging
import numpy as np
from pyiree import rt
from pyiree.tf import compiler
import tensorflow.compat.v2 as tf

flags.DEFINE_string("target_backends", None,
                    "Explicit comma-delimited list of target backends.")
flags.DEFINE_string(
    "debug_dir", None,
    "Specifies a directory to dump debug artifacts to. Defaults to "
    "--test_tmpdir")
FLAGS = flags.FLAGS

ORIGINAL_SAVED_MODEL_PATH_ATTR = "_ORIGINAL_SAVED_MODEL_PATH"

# Per test directory where debug artifacts are dumped.
global_debug_dir = None


def set_random_seed(seed=0):
  """Set random seed for tf, np and random."""
  tf.random.set_seed(seed)
  random.seed(seed)
  np.random.seed(seed)


def save_and_compile_tf_module(tf_module, exported_names=(),
                               target_backends=()):
  """Saves and compiles a TensorFlow tf.Module.

  Note that if the module has the special _ORIGINAL_SAVED_MODEL_PATH attribute,
  then it will be compiled directly from that path instead of saved and then
  loaded.

  Args:
    tf_module: A tf.Module.
    exported_names: Iterable of dotted function names to consider for
      compilation.
    target_backends: Iterable of string backend names to compile for.

  Returns:
    An _IreeCompiledModule.
  """

  def compile_from_path(sm_path):
    compiler_context = compiler.Context()
    # Break up the compilation so we can save debug artifacts.
    compiler_module = compiler.tf_load_saved_model(
        sm_path,
        exported_names=exported_names,
        compiler_context=compiler_context,
        pass_pipeline=())

    # Save the input MLIR module.
    flattened_target_backends = re.sub("[^0-9a-zA-Z_]+", "_",
                                       "__".join(target_backends))
    if global_debug_dir:
      mlir_path = os.path.join(global_debug_dir,
                               "raw__%s.mlir" % flattened_target_backends)
      logging.info("Saving raw TF input MLIR to: %s", mlir_path)
      with open(mlir_path, "w") as f:
        f.write(compiler_module.to_asm())

    # Now run the passes manually that tf_load_saved_model would usually do.
    compiler_module.run_pass_pipeline(compiler.TF_IMPORT_PASS_PIPELINE)

    if global_debug_dir:
      mlir_path = os.path.join(global_debug_dir,
                               "input__%s.mlir" % flattened_target_backends)
      logging.info("Saving IREE input MLIR to: %s", mlir_path)
      with open(mlir_path, "w") as f:
        f.write(compiler_module.to_asm())

    compiled_module = compiler_module.compile(target_backends=target_backends)
    if global_debug_dir:
      compiled_path = os.path.join(
          global_debug_dir, "compiled__%s.vmfb" % flattened_target_backends)
      logging.info("Saving compiled IREE module to: %s", compiled_path)
      with open(compiled_path, "wb") as f:
        f.write(compiled_module)

    return compiled_module

  if hasattr(tf_module, ORIGINAL_SAVED_MODEL_PATH_ATTR):
    # Compile directly from the original path.
    sm_path = getattr(tf_module, ORIGINAL_SAVED_MODEL_PATH_ATTR)
    logging.info(
        "Compiling from original saved_model path (not round-tripping): %s",
        sm_path)
    return compile_from_path(sm_path)
  else:
    options = tf.saved_model.SaveOptions(save_debug_info=True)
    if FLAGS.debug_dir is None:
      # Round-trip through a temporary directory.
      with tempfile.TemporaryDirectory() as sm_path:
        tf.saved_model.save(tf_module, sm_path, options=options)
        return compile_from_path(sm_path)
    else:
      # Use the supplied directory.
      sm_path = os.path.join(FLAGS.debug_dir, "SavedModel")
      tf.saved_model.save(tf_module, sm_path, options=options)
      return compile_from_path(sm_path)


def load_tf_module(path):
  """Wrapper around tf.saved_model.load which preserves the path.

  Args:
    path: The path to load from.

  Returns:
    The loaded module with an extra property _ORIGINAL_SAVED_MODEL_PATH added.
    This is used on subsequent compiles to load directly from the original
    path, which gives us unmolested access to the original debug information,
    which TensorFlow tends to lose on round-trip.
  """
  tf_module = tf.saved_model.load(path)
  assert not hasattr(tf_module, ORIGINAL_SAVED_MODEL_PATH_ATTR), (
      "Saved model (%s) already has attribute %s" %
      (path, ORIGINAL_SAVED_MODEL_PATH_ATTR))
  setattr(tf_module, ORIGINAL_SAVED_MODEL_PATH_ATTR, path)
  return tf_module


class CompiledModule(object):
  """Base class for per-backend compiled module facade."""

  def __init__(self, ctor, exported_names, backend):
    self._ctor = ctor
    self._exported_names = exported_names
    self._backend = backend

  @staticmethod
  def create(ctor, exported_names, backend):
    compiled_module_class = backend.CompiledModule
    return compiled_module_class(ctor, exported_names, backend)

  @property
  def ctor(self):
    return self._ctor

  def instantiate(self):
    raise NotImplementedError()


class TfCompiledModule(CompiledModule):
  """TensorFlow 'compiled' module.

  This just wraps the constructor.
  """

  def instantiate(self):
    tf_module = self.ctor()
    return _TfModuleInstance(tf_module)


class _TfModuleInstance(object):
  """Instance of a TF module."""

  def __init__(self, tf_module):
    self._tf_module = tf_module

  def __getattr__(self, attr):
    # Try to resolve it as a function.
    if not hasattr(self._tf_module, attr):
      raise AttributeError("The TensorFlow module does not have attr '%s'" %
                           (attr,))
    f = getattr(self._tf_module, attr)
    if not f or not hasattr(f, "__call__"):
      raise AttributeError(
          "The TensorFlow module does not have a callable attr '%s'" % (attr,))
    return _TfFunctionWrapper(f)


class _TfFunctionWrapper(object):
  """Wraps a TF function, normalizing it to numpy."""

  def __init__(self, f):
    self._f = f

  def __call__(self, *args, **kwargs):
    # TensorFlow will auto-convert all inbound args.
    results = self._f(*args, **kwargs)
    # Then unmarshal them to numpy in the same way that the other backends do.
    # Handle single result (technically ambiguous with return of a tuple,
    # which is sad).
    if not isinstance(results, tuple):
      results = (results,)
    return tf.nest.map_structure(
        lambda t: t.numpy() if isinstance(t, tf.Tensor) else t,
        *results,
        check_types=False)


class IreeCompiledModule(CompiledModule):
  """Iree compiled module."""

  def __init__(self, ctor, exported_names, backend):
    super().__init__(ctor, exported_names, backend)
    self._iree_module_blob = save_and_compile_tf_module(
        ctor(),
        exported_names=exported_names,
        target_backends=backend.iree_compiler_targets)
    self._iree_module = rt.VmModule.from_flatbuffer(self._iree_module_blob)

  def instantiate(self):
    return _IreeModuleInstance(self._backend, self._iree_module_blob,
                               self._iree_module)


class _IreeModuleInstance(object):
  """An instance of an IREE module."""

  def __init__(self, backend, iree_module_blob, iree_module):
    self._backend = backend
    self._iree_module_blob = iree_module_blob
    self._iree_module = iree_module
    self._iree_module_name = self._iree_module.name

    self._system_config = rt.Config(driver_name=backend.iree_driver)
    self._context = rt.SystemContext(
        modules=[self._iree_module], config=self._system_config)

  def __getattr__(self, attr):
    # Try to resolve it as a function.
    m = self._context.modules[self._iree_module_name]
    f = m[attr]
    return _IreeFunctionWrapper(self._context, f)


class _IreeFunctionWrapper(object):
  """Wraps an IREE function, making it callable."""

  def __init__(self, context, f):
    self._context = context
    self._f = f

  def __call__(self, *args):
    return self._f(*args)


class _VirtualModuleInstance(object):
  """Wraps a namedtuple of modules and represents a union of them."""

  def __init__(self, named_modules, match_spec):
    self._named_modules = named_modules
    self._match_spec = match_spec

  def __getattr__(self, attr):
    match_modules = {
        k: v
        for k, v in self._named_modules.items()
        if re.search(self._match_spec, k)
    }
    if not match_modules:
      raise AttributeError(
          "Module match spec '%s' did not match anything. (Have %r)" %
          (self._match_spec, self._named_modules.keys()))
    # Resolve functions on each.
    match_functions = {}
    for backend, module in match_modules.items():
      try:
        match_functions[backend] = getattr(module, attr)
      except:
        raise AttributeError(
            "Could not resolve function '%s' on backend module '%s'" %
            (attr, backend))
    return _VirtualFunctionWrapper(match_functions)


class _VirtualFunctionWrapper(object):
  """Wrapper around a virtual dict of functions."""

  def __init__(self, backend_function_dict):
    self._backend_function_dict = backend_function_dict

  def __call__(self, *args, **kwargs):
    all_results = {
        backend: f(*args, **kwargs)
        for backend, f in self._backend_function_dict.items()
    }
    # Turn it into a named tuple so we get nice class-like access to it.
    results_tuple_class = collections.namedtuple("Results", all_results.keys())
    return _make_multi_result_class(results_tuple_class)(*all_results.values())


def _recursive_check_same(result_ref, result_tgt, rtol=1e-6, atol=1e-6):
  same = True
  if not isinstance(result_tgt, type(result_ref)):
    raise ValueError("Types of the outputs must be the same, but have '{}' and "
                     "'{}'".format(type(result_ref), type(result_tgt)))
  if isinstance(result_ref, dict):
    if result_ref.keys() != result_tgt.keys():
      raise ValueError("Outputs must have the same structure, but have '{}' and"
                       " '{}'".format(result_ref.keys(), result_tgt.keys()))
    for key in result_ref.keys():
      same = same and _recursive_check_same(result_ref[key], result_tgt[key],
                                            rtol, atol)
      if not same:
        return False  # no need to go further they are different
  elif isinstance(result_ref, list):
    if len(result_ref) != len(result_tgt):
      raise ValueError("Outputs must have the same structure, but have '{}' and"
                       " '{}'".format(result_ref, result_tgt))
    for i in range(len(result_ref)):
      same = same and _recursive_check_same(result_ref[i], result_tgt[i], rtol,
                                            atol)
      if not same:
        return False  # no need to go further they are different
  elif isinstance(result_ref, np.ndarray):
    if isinstance(result_ref.flat[0], np.floating):
      return np.allclose(result_ref, result_tgt, rtol=rtol, atol=atol)
    else:
      return np.array_equal(result_ref, result_tgt)
  else:
    # this one need more checks
    return result_ref == result_tgt
  return same


def _collect_disagreements_recursively(mr, rtol=1e-6, atol=1e-6):
  """Compare result structs recursively and search for disagreements.

  Args:
    mr: A MultiResults namedtuple where each entry corresponds to a backend set
      of results.
    rtol: The relative tolerance parameter.
    atol: The absolute tolerance parameter.

  Returns:
    An equivalent MultiResults where each entry is an array of result names
    that disagree.
  """
  has_disagreement = False
  disagreement_list = [list() for _ in mr]
  for i in range(len(mr)):
    result_ref = mr[i]
    for j in range(len(mr)):
      if i < j:
        continue  # Don't check self and reverse comparisons
      result_tgt = mr[j]
      if not _recursive_check_same(result_ref, result_tgt, rtol, atol):
        has_disagreement = True
        disagreement_list[i].append(mr._fields[j])
  disagreements_tuple = collections.namedtuple("Disagreements", mr._fields)
  return has_disagreement, disagreements_tuple(*disagreement_list)


def _collect_disagreements(mr, predicate):
  """Verifies that result structs.

  Args:
    mr: A MultiResults namedtuple where each entry corresponds to a backend set
      of results.
    predicate: A predicate function which takes (a, b) and returns whether they
      should be considered equivalent.

  Returns:
    An equivalent MultiResults where each entry is an array of result names
    that disagree.
  """
  has_disagreement = False
  disagreement_list = [list() for _ in mr]
  for i in range(len(mr)):
    result_ref = mr[i]
    for j in range(len(mr)):
      if i == j:
        continue  # Don't check self.
      result_tgt = mr[j]
      if not predicate(result_ref, result_tgt):
        has_disagreement = True
        disagreement_list[i].append(mr._fields[j])
  disagreements_tuple = collections.namedtuple("Disagreements", mr._fields)
  return has_disagreement, disagreements_tuple(*disagreement_list)


def _make_multi_result_class(named_tuple_class):
  """Makes a class that wraps a mapping of backend results."""

  class MultiResults(named_tuple_class):
    """Wraps a mapping of results."""

    def assert_all_close(self, rtol=1e-6, atol=1e-6):
      predicate = (lambda a, b: np.allclose(a, b, rtol=rtol, atol=atol))
      has_disagreement, disagreements = _collect_disagreements(self, predicate)
      assert not has_disagreement, ("Multiple backends disagree (%r):\n%r" %
                                    (disagreements, self))
      return self

    def assert_all_equal(self):
      predicate = np.array_equal
      has_disagreement, disagreements = _collect_disagreements(self, predicate)
      assert not has_disagreement, ("Multiple backends disagree (%r):\n%r" %
                                    (disagreements, self))
      return self

    def assert_all_close_and_equal(self, rtol=1e-6, atol=1e-6):
      # it is a special case when output can be a nestet map of dict(), list()
      # with different types: int, float, string
      # in this case int and string must be equal and for float we use rtol,atol
      has_disagreement, disagreements = _collect_disagreements_recursively(
          self, rtol, atol)
      assert not has_disagreement, ("Multiple backends disagree (%r):\n%r" %
                                    (disagreements, self))
      return self

    def print(self):
      print(self)
      return self

    def save(self):
      if FLAGS.debug_dir:
        for i in range(len(self)):
          result = self[i]  # output generated by a model
          field = self._fields[i]  # backend name
          fname = os.path.join(FLAGS.debug_dir, "output_{}".format(field))
          with open(fname, "w") as file:
            # content of txt file can be converted to py objects by eval(txt)
            file.write(str(result))
      return self

  return MultiResults


def _instantiate_modules(compiled_modules_dict):
  """Given a dict of modules, instantiates them.

  Args:
    compiled_modules_dict: Dictionary of
        {module_name:{backend_name:CompiledModule}} that should be instantiated.

  Returns:
    namedtuple mapping module_key:VirtualBackendsClass for every module
    in compiled_modules_dict. The VirtualBackendsClass is a dynamically
    generated namedtuple mapping backend_name:ModuleInstance, where the
    ModuleInstance allows attribute resolution of public functions on the
    module. The VirtualBackendsClass also contributes some convenience
    methods for selecting all or a subset of matching backend modules.
  """

  def instantiate_backends(module_dict):
    """Creates a VirtualBackend namedtuple class for a dict.

    Args:
      module_dict: Dictionary of backend_name:ModuleInstance.

    Returns:
      namedtuple subclass with a field for every backend and special
      all and multi() helpers.
    """
    tuple_class = collections.namedtuple("VirtualBackendsTuple",
                                         module_dict.keys())

    class VirtualBackendsClass(tuple_class):
      """Adds a __call__ method that creates a virtual module."""

      def multi(self, match_spec="."):
        """Selects multiple backends that match a regular expression."""
        return _VirtualModuleInstance(self._asdict(), match_spec)

      @property
      def all(self):
        """Shorthand for multi() which selects all backends."""
        return self.multi()

    return VirtualBackendsClass(
        *[m.instantiate() for m in module_dict.values()])

  module_keys = [k for (k, _) in compiled_modules_dict.items()]
  module_insts = [
      instantiate_backends(module_dict)
      for (_, module_dict) in compiled_modules_dict.items()
  ]
  tuple_class = collections.namedtuple("Modules", module_keys)
  return tuple_class(*module_insts)


def compile_modules(**kwargs):
  """Decorator applied to a SavedModelTestCase subclass to compile modules.

  Args:
    **kwargs: name/Module constructor mappings. Each such arg will be added to
      the classes 'compiled_modules' field.

  Returns:
    Class decorator function.
  """

  def decorator(cls):
    """Decorator function."""
    assert issubclass(cls, SavedModelTestCase), (
        "The 'compile_modules' decorator must be applied to a "
        "SavedModelTestCase derived class.")
    if not cls._modules_to_compile:
      cls._modules_to_compile = {}
    for name, ctor in kwargs.items():
      assert name not in cls._modules_to_compile, (
          "@compile_modules called with duplicate module names '%s'" % (name,))
      exported_names = ()
      if isinstance(ctor, tuple):
        ctor, exported_names = ctor
      cls._modules_to_compile[name] = (ctor, exported_names)

    return cls

  return decorator


class BackendInfo(
    collections.namedtuple(
        "BackendInfo",
        ["name", "CompiledModule", "iree_driver", "iree_compiler_targets"])):
  """Info object describing a backend."""

  # All BackendInfo entries by name.
  ALL = {}

  @classmethod
  def add(cls, **kwargs):
    backend_info = cls(**kwargs)
    cls.ALL[backend_info.name] = backend_info


BackendInfo.add(
    name="tf",
    CompiledModule=TfCompiledModule,
    iree_driver=None,
    iree_compiler_targets=None)
# tf_also is used for checking test consistency
# to catch any initialization/randomization issues between model runs
BackendInfo.add(
    name="tf_also",
    CompiledModule=TfCompiledModule,
    iree_driver=None,
    iree_compiler_targets=None)
BackendInfo.add(
    name="iree_vmla",
    CompiledModule=IreeCompiledModule,
    iree_driver="vmla",
    iree_compiler_targets=["vmla"])
BackendInfo.add(
    name="iree_vulkan",
    CompiledModule=IreeCompiledModule,
    iree_driver="vulkan",
    iree_compiler_targets=["vulkan-*"])
BackendInfo.add(
    name="iree_llvmjit",
    CompiledModule=IreeCompiledModule,
    iree_driver="llvm",
    iree_compiler_targets=["llvm-ir"])


def _parse_target_backends(target_backends):
  """Decodes a comma-delimited string of backends into BackendInfo objects."""
  backends = []
  for backend_name in target_backends.split(","):
    if backend_name not in BackendInfo.ALL.keys():
      raise ValueError(
          "Invalid backend specification string '{}', unexpected name '{}';"
          " valid names are '{}'".format(target_backends, backend_name,
                                         BackendInfo.ALL.keys()))
    backends.append(BackendInfo.ALL[backend_name])
  return backends


def get_backends():
  """Gets the BackendInfo instances to test.

  By default all backends in BackendInfo will be used. Specific backends to
  run on can be specified using the `--target_backends` flag. If only "tf" is
  provided then it will be compared against itself.

  Returns:
    Sequence of BackendInfo that should be used.
  """
  if FLAGS.target_backends is not None:
    logging.info("Using backends from command line: %s", FLAGS.target_backends)
    backends = _parse_target_backends(FLAGS.target_backends)
    # If tf is the only backend then we will test it itself by adding tf_also.
    if len(backends) == 1 and "tf" == backends[0].name:
      backends.append(BackendInfo.ALL["tf_also"])
  else:
    # If no backends are specified, use them all.
    backends = list(BackendInfo.ALL.values())
  return backends


class SavedModelTestCase(tf.test.TestCase):
  """Tests against a SavedModel."""

  # Will be initialized to a dict by the @compile_modules decorator.
  # The dict maps module name to (ctor, exported_names, backend_names).
  _modules_to_compile = None

  # Will be initialized in setUpClass to a dict of (name, CompiledModule)
  # instances mirroring _modules_to_compile.
  compiled_modules = None

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.modules = None

  @classmethod
  def setUpClass(cls):
    super().setUpClass()
    cls.compiled_modules = {}
    if cls._modules_to_compile:
      for name, (ctor, exported_names) in cls._modules_to_compile.items():

        # Setup the debug directory.
        debug_parent_dir = FLAGS.debug_dir
        if not debug_parent_dir:
          debug_parent_dir = FLAGS.test_tmpdir
        debug_parent_dir = os.path.join(debug_parent_dir, cls.__name__)

        try:
          os.makedirs(debug_parent_dir)
        except IOError:
          logging.exception("Error creating crash reproducer dir for: %s",
                            debug_parent_dir)

        # Setup crash reproducer and global debug dir.
        crash_reproducer_path = os.path.join(debug_parent_dir,
                                             name + "_reproducer.mlir")
        compiler.Context.default_crash_reproducer_path = crash_reproducer_path
        global global_debug_dir
        global_debug_dir = debug_parent_dir

        try:
          # Compile.
          backends = get_backends()
          cls.compiled_modules[name] = dict([
              (backend.name, CompiledModule.create(ctor, exported_names,
                                                   backend))
              for backend in backends
          ])
        finally:
          # Disable crash reproducer (to avoid inadvertently overwriting this
          # path on a subsequent interaction).
          compiler.Context.default_crash_reproducer_path = None
          global_debug_dir = None

  @classmethod
  def tearDownClass(cls):
    super().tearDownClass()

  def setUp(self):
    super().setUp()
    self.modules = _instantiate_modules(self.compiled_modules)
