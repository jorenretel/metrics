# Copyright The Lightning team.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from typing import Any, Literal, Optional, Sequence, Union

import torch
from torch import Tensor, tensor

from torchmetrics.functional.regression.mse import _mean_squared_error_compute, _mean_squared_error_update
from torchmetrics.metric import Metric
from torchmetrics.utilities.imports import _MATPLOTLIB_AVAILABLE
from torchmetrics.utilities.plot import _AX_TYPE, _PLOT_OUT_TYPE

if not _MATPLOTLIB_AVAILABLE:
    __doctest_skip__ = ["MeanSquaredError.plot"]


class MeanSquaredError(Metric):
    r"""Compute `mean squared error`_ (MSE).

    .. math:: \text{MSE} = \frac{1}{N}\sum_i^N(y_i - \hat{y_i})^2

    Where :math:`y` is a tensor of target values, and :math:`\hat{y}` is a tensor of predictions.

    As input to ``forward`` and ``update`` the metric accepts the following input:

    - ``preds`` (:class:`~torch.Tensor`): Predictions from model
    - ``target`` (:class:`~torch.Tensor`): Ground truth values

    As output of ``forward`` and ``compute`` the metric returns the following output:

    - ``mean_squared_error`` (:class:`~torch.Tensor`): A tensor with the mean squared error

    Args:
        squared: If True returns MSE value, if False returns RMSE value.
        num_outputs: shape of outputs in multioutput setting.
        reduce_dims: dimensions to reduce. Defaults to "all" meaning
            a single number will be produced. The remaing shape should
            have the shape num_outputs.
        kwargs: Additional keyword arguments, see :ref:`Metric kwargs` for more info.

    Example::
        Single output mse computation:

        >>> from torch import tensor
        >>> from torchmetrics.regression import MeanSquaredError
        >>> target = tensor([2.5, 5.0, 4.0, 8.0])
        >>> preds = tensor([3.0, 5.0, 2.5, 7.0])
        >>> mean_squared_error = MeanSquaredError()
        >>> mean_squared_error(preds, target)
        tensor(0.8750)

    Example::
        Multioutput mse computation:

        >>> from torch import tensor
        >>> from torchmetrics.regression import MeanSquaredError
        >>> target = tensor([[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]])
        >>> preds = tensor([[1.0, 2.0, 3.0], [1.0, 2.0, 3.0]])
        >>> mean_squared_error = MeanSquaredError(num_outputs=3)
        >>> mean_squared_error(preds, target)
        tensor([1., 4., 9.])

    """
    is_differentiable = True
    higher_is_better = False
    full_state_update = False
    plot_lower_bound: float = 0.0

    sum_squared_error: Tensor
    total: Tensor

    def __init__(
        self,
        squared: bool = True,
        num_outputs: int | tuple[int] = 1,
        reduce_dims: int | tuple[int] | Literal["all"] = "all",
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)

        if not isinstance(squared, bool):
            raise ValueError(f"Expected argument `squared` to be a boolean but got {squared}")
        self.squared = squared

        if not (isinstance(num_outputs, int) and num_outputs > 0) and not (
            isinstance(num_outputs, tuple)
            and all(isinstance(dim_size, int) and dim_size > 0 for dim_size in num_outputs)
        ):
            print(num_outputs)
            raise ValueError(
                f"Expected num_outputs to be a positive integer or a tuple of positive integers but got {num_outputs}"
            )
        self.output_size = num_outputs

        if (
            not isinstance(reduce_dims, int)
            and not (isinstance(reduce_dims, tuple) and all(isinstance(dim, int) for dim in reduce_dims))
            and not reduce_dims == "all"
        ):
            raise ValueError(
                f'Expected reduce_dimensions to be an integer, a tuple of integers or "all" but got {reduce_dims}'
            )

        if reduce_dims == "all":
            reduce_dims = None
        self.reduce_dimensions = reduce_dims

        self.add_state("sum_squared_error", default=torch.zeros(num_outputs), dist_reduce_fx="sum")
        self.add_state("total", default=tensor(0), dist_reduce_fx="sum")

    def update(self, preds: Tensor, target: Tensor) -> None:
        """Update state with predictions and targets."""
        sum_squared_error, n_obs = _mean_squared_error_update(preds, target, reduce_dims=self.reduce_dimensions)

        self.sum_squared_error += sum_squared_error
        self.total += n_obs

    def compute(self) -> Tensor:
        """Compute mean squared error over state."""
        return _mean_squared_error_compute(self.sum_squared_error, self.total, squared=self.squared)

    def plot(
        self, val: Optional[Union[Tensor, Sequence[Tensor]]] = None, ax: Optional[_AX_TYPE] = None
    ) -> _PLOT_OUT_TYPE:
        """Plot a single or multiple values from the metric.

        Args:
            val: Either a single result from calling `metric.forward` or `metric.compute` or a list of these results.
                If no value is provided, will automatically call `metric.compute` and plot that result.
            ax: An matplotlib axis object. If provided will add plot to that axis

        Returns:
            Figure and Axes object

        Raises:
            ModuleNotFoundError:
                If `matplotlib` is not installed

        .. plot::
            :scale: 75

            >>> from torch import randn
            >>> # Example plotting a single value
            >>> from torchmetrics.regression import MeanSquaredError
            >>> metric = MeanSquaredError()
            >>> metric.update(randn(10,), randn(10,))
            >>> fig_, ax_ = metric.plot()

        .. plot::
            :scale: 75

            >>> from torch import randn
            >>> # Example plotting multiple values
            >>> from torchmetrics.regression import MeanSquaredError
            >>> metric = MeanSquaredError()
            >>> values = []
            >>> for _ in range(10):
            ...     values.append(metric(randn(10,), randn(10,)))
            >>> fig, ax = metric.plot(values)

        """
        return self._plot(val, ax)


# if __name__ == "__main__":
#     from torch import tensor
#
#     target = tensor([2.5, 5.0, 4.0, 8.0])
#     preds = tensor([3.0, 5.0, 2.5, 7.0])
#     mean_squared_error = MeanSquaredError()
#     print(mean_squared_error(preds, target))
#
#     target = torch.rand(size=(2, 5, 7))
#     preds = pred = target + 2
#
#     mean_squared_error = MeanSquaredError()
#     print(mean_squared_error(preds, target))
#
#     mean_squared_error = MeanSquaredError(num_outputs=5, reduce_dims=(0, 2))
#     print(mean_squared_error(preds, target))
