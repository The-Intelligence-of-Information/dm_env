# pylint: disable=g-bad-file-header
# Copyright 2019 The dm_env Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or  implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ============================================================================
"""Classes that describe numpy arrays."""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import numpy as np

_INVALID_SHAPE = 'Expected shape %r but found %r'
_INVALID_DTYPE = 'Expected dtype %r but found %r'
_OUT_OF_BOUNDS = 'Values were not all within bounds %s <= %s <= %s'


class Array(object):
  """Describes a numpy array or scalar shape and dtype.

  An `Array` spec allows an API to describe the arrays that it accepts or
  returns, before that array exists.
  The equivalent version describing a `tf.Tensor` is `TensorSpec`.
  """
  __slots__ = ('_shape', '_dtype', '_name')
  __hash__ = None

  def __init__(self, shape, dtype, name=None):
    """Initializes a new `Array` spec.

    Args:
      shape: An iterable specifying the array shape.
      dtype: numpy dtype or string specifying the array dtype.
      name: Optional string containing a semantic name for the corresponding
        array. Defaults to `None`.

    Raises:
      TypeError: If `shape` is not an iterable of elements convertible to int,
      or if `dtype` is not convertible to a numpy dtype.
    """
    self._shape = tuple(int(dim) for dim in shape)
    self._dtype = np.dtype(dtype)
    self._name = name

  @property
  def shape(self):
    """Returns a `tuple` specifying the array shape."""
    return self._shape

  @property
  def dtype(self):
    """Returns a numpy dtype specifying the array dtype."""
    return self._dtype

  @property
  def name(self):
    """Returns the name of the Array."""
    return self._name

  def __repr__(self):
    return 'Array(shape={}, dtype={}, name={})'.format(self.shape,
                                                       repr(self.dtype),
                                                       repr(self.name))

  def __eq__(self, other):
    """Checks if the shape and dtype of two specs are equal."""
    if not isinstance(other, Array):
      return False
    return self.shape == other.shape and self.dtype == other.dtype

  def __ne__(self, other):
    return not self == other

  def _fail_validation(self, message, *args):
    message %= args
    if self.name:
      message += ' for spec %s' % self.name
    raise ValueError(message)

  def validate(self, value):
    """Checks if value conforms to this spec.

    Args:
      value: a numpy array or value convertible to one via `np.asarray`.

    Returns:
      value, converted if necessary to a numpy array.

    Raises:
      ValueError: if value doesn't conform to this spec.
    """
    value = np.asarray(value)
    if value.shape != self.shape:
      self._fail_validation(_INVALID_SHAPE, self.shape, value.shape)
    if value.dtype != self.dtype:
      self._fail_validation(_INVALID_DTYPE, self.dtype, value.dtype)
    return value

  def generate_value(self):
    """Generate a test value which conforms to this spec."""
    return np.zeros(shape=self.shape, dtype=self.dtype)

  def __reduce__(self):
    return Array, (self._shape, self._dtype, self._name)


class BoundedArray(Array):
  """An `Array` spec that specifies minimum and maximum values.

  Example usage:
  ```python
  # Specifying the same minimum and maximum for every element.
  spec = BoundedArray((3, 4), np.float64, minimum=0.0, maximum=1.0)

  # Specifying a different minimum and maximum for each element.
  spec = BoundedArray(
      (2,), np.float64, minimum=[0.1, 0.2], maximum=[0.9, 0.9])

  # Specifying the same minimum and a different maximum for each element.
  spec = BoundedArray(
      (3,), np.float64, minimum=-10.0, maximum=[4.0, 5.0, 3.0])
  ```

  Bounds are meant to be inclusive. This is especially important for
  integer types. The following spec will be satisfied by arrays
  with values in the set {0, 1, 2}:
  ```python
  spec = BoundedArray((3, 4), np.int, minimum=0, maximum=2)
  ```
  """
  __slots__ = ('_minimum', '_maximum')
  __hash__ = None

  def __init__(self, shape, dtype, minimum, maximum, name=None):
    """Initializes a new `BoundedArray` spec.

    Args:
      shape: An iterable specifying the array shape.
      dtype: numpy dtype or string specifying the array dtype.
      minimum: Number or sequence specifying the minimum element bounds
        (inclusive). Must be broadcastable to `shape`.
      maximum: Number or sequence specifying the maximum element bounds
        (inclusive). Must be broadcastable to `shape`.
      name: Optional string containing a semantic name for the corresponding
        array. Defaults to `None`.

    Raises:
      ValueError: If `minimum` or `maximum` are not broadcastable to `shape`.
      TypeError: If the shape is not an iterable or if the `dtype` is an invalid
        numpy dtype.
    """
    super(BoundedArray, self).__init__(shape, dtype, name)

    try:
      np.broadcast_to(minimum, shape=shape)
    except ValueError as numpy_exception:
      raise ValueError('minimum is not compatible with shape. '
                       'Message: {!r}.'.format(numpy_exception))

    try:
      np.broadcast_to(maximum, shape=shape)
    except ValueError as numpy_exception:
      raise ValueError('maximum is not compatible with shape. '
                       'Message: {!r}.'.format(numpy_exception))

    self._minimum = np.array(minimum)
    self._minimum.setflags(write=False)

    self._maximum = np.array(maximum)
    self._maximum.setflags(write=False)

  @property
  def minimum(self):
    """Returns a NumPy array specifying the minimum bounds (inclusive)."""
    return self._minimum

  @property
  def maximum(self):
    """Returns a NumPy array specifying the maximum bounds (inclusive)."""
    return self._maximum

  def __repr__(self):
    template = ('BoundedArray(shape={}, dtype={}, name={}, '
                'minimum={}, maximum={})')
    return template.format(self.shape, repr(self.dtype), repr(self.name),
                           self._minimum, self._maximum)

  def __eq__(self, other):
    if not isinstance(other, BoundedArray):
      return False
    return (super(BoundedArray, self).__eq__(other) and
            (self.minimum == other.minimum).all() and
            (self.maximum == other.maximum).all())

  def validate(self, value):
    value = np.asarray(value)
    super(BoundedArray, self).validate(value)
    if (value < self.minimum).any() or (value > self.maximum).any():
      self._fail_validation(_OUT_OF_BOUNDS, self.minimum, value, self.maximum)
    return value

  def generate_value(self):
    return (np.ones(shape=self.shape, dtype=self.dtype) *
            self.dtype.type(self.minimum))

  def __reduce__(self):
    return BoundedArray, (self._shape, self._dtype, self._minimum,
                          self._maximum, self._name)


_NUM_VALUES_NOT_POSITIVE = '`num_values` must be a positive integer, got {}.'
_DTYPE_NOT_INTEGRAL = '`dtype` must be integral, got {}.'
_DTYPE_OVERFLOW = (
    '`dtype` {} is not big enough to hold `num_values` ({}) without overflow.')


class DiscreteArray(BoundedArray):
  """Represents a discrete, scalar, zero-based space.

  Concretely this is a 0-dimensional numpy array containing a single integer
  value between 0 and num_items - 1 (inclusive).
  """

  _REPR_TEMPLATE = (
      'DiscreteArray(shape={self.shape}, dtype={self.dtype}, name={self.name}, '
      'minimum={self.minimum}, maximum={self.maximum}, '
      'num_values={self.num_values})')

  __slots__ = ('_num_values',)

  def __init__(self, num_values, dtype=np.int32, name=None):
    """Initializes a new `DiscreteArray` spec.

    Args:
      num_values: Integer specifying the number of possible values to represent.
      dtype: The dtype of the array. Must be an integral type large enough to
        hold `num_values` without overflow.
      name: Optional string specifying the name of the array.

    Raises:
      ValueError: If `num_values` is not positive, if `dtype` is not integral,
        or if `dtype` is not large enough to hold `num_values` without overflow.
    """
    if num_values <= 0 or not np.issubdtype(type(num_values), np.integer):
      raise ValueError(_NUM_VALUES_NOT_POSITIVE.format(num_values))

    if not np.issubdtype(dtype, np.integer):
      raise ValueError(_DTYPE_NOT_INTEGRAL.format(dtype))

    num_values = int(num_values)
    maximum = num_values - 1
    dtype = np.dtype(dtype)

    if np.min_scalar_type(maximum) > dtype:
      raise ValueError(_DTYPE_OVERFLOW.format(dtype, num_values))

    super(DiscreteArray, self).__init__(
        shape=(),
        dtype=dtype,
        minimum=0,
        maximum=maximum,
        name=name)
    self._num_values = num_values

  @property
  def num_values(self):
    """Returns the number of items."""
    return self._num_values

  def __repr__(self):
    return self._REPR_TEMPLATE.format(self=self)

  def __reduce__(self):
    return DiscreteArray, (self._num_values, self._dtype, self._name)