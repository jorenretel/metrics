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
from collections import namedtuple
from functools import partial

import pytest
import torch
from sklearn.metrics import mean_tweedie_deviance
from torch import Tensor
from torchmetrics.functional.regression.tweedie_deviance import tweedie_deviance_score
from torchmetrics.regression.tweedie_deviance import TweedieDevianceScore
from torchmetrics.utilities.imports import _TORCH_GREATER_EQUAL_1_9

from unittests import BATCH_SIZE, NUM_BATCHES
from unittests.helpers import seed_all
from unittests.helpers.testers import MetricTester

seed_all(42)

Input = namedtuple("Input", ["preds", "targets"])

_single_target_inputs1 = Input(
    preds=torch.rand(NUM_BATCHES, BATCH_SIZE),
    targets=torch.rand(NUM_BATCHES, BATCH_SIZE),
)

_single_target_inputs2 = Input(
    preds=torch.rand(NUM_BATCHES, BATCH_SIZE),
    targets=torch.rand(NUM_BATCHES, BATCH_SIZE),
)

_multi_target_inputs = Input(
    preds=torch.rand(NUM_BATCHES, BATCH_SIZE, 5),
    targets=torch.rand(NUM_BATCHES, BATCH_SIZE, 5),
)


def _sklearn_deviance(preds: Tensor, targets: Tensor, power: float):
    sk_preds = preds.view(-1).numpy()
    sk_target = targets.view(-1).numpy()
    return mean_tweedie_deviance(sk_target, sk_preds, power=power)


@pytest.mark.parametrize("power", [-0.5, 0, 1, 1.5, 2, 3])
@pytest.mark.parametrize(
    "preds, targets",
    [
        (_single_target_inputs1.preds, _single_target_inputs1.targets),
        (_single_target_inputs2.preds, _single_target_inputs2.targets),
        (_multi_target_inputs.preds, _multi_target_inputs.targets),
    ],
)
class TestDevianceScore(MetricTester):
    """Test class for `TweedieDevianceScore` metric."""

    @pytest.mark.parametrize("ddp", [True, False])
    def test_deviance_scores_class(self, ddp, preds, targets, power):
        """Test class implementation of metric."""
        self.run_class_metric_test(
            ddp,
            preds,
            targets,
            TweedieDevianceScore,
            partial(_sklearn_deviance, power=power),
            metric_args={"power": power},
        )

    def test_deviance_scores_functional(self, preds, targets, power):
        """Test functional implementation of metric."""
        self.run_functional_metric_test(
            preds,
            targets,
            tweedie_deviance_score,
            partial(_sklearn_deviance, power=power),
            metric_args={"power": power},
        )

    def test_deviance_scores_differentiability(self, preds, targets, power):
        """Test the differentiability of the metric, according to its `is_differentiable` attribute."""
        self.run_differentiability_test(
            preds, targets, metric_module=TweedieDevianceScore, metric_functional=tweedie_deviance_score
        )

    # Tweedie Deviance Score half + cpu does not work for power=[1,2] due to missing support in torch.log
    def test_deviance_scores_half_cpu(self, preds, targets, power):
        """Test dtype support of the metric on CPU."""
        if not _TORCH_GREATER_EQUAL_1_9 or power in [1, 2]:
            pytest.xfail(reason="TweedieDevianceScore metric does not support cpu + half precision for older Pytorch")
        metric_args = {"power": power}
        self.run_precision_test_cpu(
            preds,
            targets,
            metric_module=TweedieDevianceScore,
            metric_functional=tweedie_deviance_score,
            metric_args=metric_args,
        )

    @pytest.mark.skipif(not torch.cuda.is_available(), reason="test requires cuda")
    def test_deviance_scores_half_gpu(self, preds, targets, power):
        """Test dtype support of the metric on GPU."""
        metric_args = {"power": power}
        self.run_precision_test_gpu(
            preds,
            targets,
            metric_module=TweedieDevianceScore,
            metric_functional=tweedie_deviance_score,
            metric_args=metric_args,
        )


def test_error_on_different_shape(metric_class=TweedieDevianceScore):
    """Test that error is raised on different shapes of input."""
    metric = metric_class()
    with pytest.raises(RuntimeError, match="Predictions and targets are expected to have the same shape"):
        metric(torch.randn(100), torch.randn(50))


def test_error_on_invalid_inputs(metric_class=TweedieDevianceScore):
    """Test that error is raised on wrong argument combinations."""
    with pytest.raises(ValueError, match="Deviance Score is not defined for power=0.5."):
        metric_class(power=0.5)

    metric = metric_class(power=1)
    with pytest.raises(
        ValueError, match="For power=1, 'preds' has to be strictly positive and 'targets' cannot be negative."
    ):
        metric(torch.tensor([-1.0, 2.0, 3.0]), torch.rand(3))

    with pytest.raises(
        ValueError, match="For power=1, 'preds' has to be strictly positive and 'targets' cannot be negative."
    ):
        metric(torch.rand(3), torch.tensor([-1.0, 2.0, 3.0]))

    metric = metric_class(power=2)
    with pytest.raises(ValueError, match="For power=2, both 'preds' and 'targets' have to be strictly positive."):
        metric(torch.tensor([-1.0, 2.0, 3.0]), torch.rand(3))

    with pytest.raises(ValueError, match="For power=2, both 'preds' and 'targets' have to be strictly positive."):
        metric(torch.rand(3), torch.tensor([-1.0, 2.0, 3.0]))


def test_corner_case_for_power_at_1(metric_class=TweedieDevianceScore):
    """Test that corner case for power=1.0 produce valid result."""
    metric = TweedieDevianceScore()
    targets = torch.tensor([0, 1, 0, 1])
    preds = torch.tensor([0.1, 0.1, 0.1, 0.1])
    val = metric(preds, targets)
    assert val != 0.0
    assert not torch.isnan(val)
