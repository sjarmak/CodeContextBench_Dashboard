"""Tests for validate_patch_cross_repo.py per-repo weighted scoring."""

import json
import os
import tempfile
from unittest import mock

import pytest

# Add benchmarks/10figure/scripts to path for import
import sys

sys.path.insert(
    0,
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "benchmarks",
        "10figure",
        "scripts",
    ),
)

from validate_patch_cross_repo import (
    split_patch_by_repo,
    validate_weights,
    validate_cross_repo,
    run_base_validator,
)


class TestValidateWeights:
    """Tests for weight validation."""

    def test_valid_weights_sum_to_one(self):
        """Weights that sum to 1.0 should pass validation."""
        validate_weights({"kubernetes": 0.6, "envoy": 0.4})

    def test_valid_weights_with_tolerance(self):
        """Weights within 0.01 tolerance should pass."""
        validate_weights({"kubernetes": 0.6, "envoy": 0.395})

    def test_invalid_weights_sum_not_one(self):
        """Weights that don't sum to 1.0 should fail."""
        with pytest.raises(SystemExit):
            validate_weights({"kubernetes": 0.5, "envoy": 0.3})

    def test_invalid_negative_weight(self):
        """Negative weights should fail."""
        with pytest.raises(SystemExit):
            validate_weights({"kubernetes": 1.5, "envoy": -0.5})


class TestSplitPatchByRepo:
    """Tests for patch splitting by repository."""

    def test_split_two_repos(self):
        """Combined patch should split into per-repo patches."""
        patch_content = (
            "diff --git a/src/kubernetes/pkg/foo.go b/src/kubernetes/pkg/foo.go\n"
            "--- a/src/kubernetes/pkg/foo.go\n"
            "+++ b/src/kubernetes/pkg/foo.go\n"
            "@@ -1,3 +1,3 @@\n"
            " line1\n"
            "-old\n"
            "+new\n"
            "diff --git a/src/envoy/source/bar.cc b/src/envoy/source/bar.cc\n"
            "--- a/src/envoy/source/bar.cc\n"
            "+++ b/src/envoy/source/bar.cc\n"
            "@@ -1,3 +1,3 @@\n"
            " line1\n"
            "-old2\n"
            "+new2\n"
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".patch", delete=False) as f:
            f.write(patch_content)
            patch_file = f.name

        try:
            result = split_patch_by_repo(patch_file, ["kubernetes", "envoy"])

            assert "kubernetes" in result
            assert "envoy" in result

            with open(result["kubernetes"]) as f:
                k8s_patch = f.read()
            assert "kubernetes/pkg/foo.go" in k8s_patch
            assert "envoy" not in k8s_patch

            with open(result["envoy"]) as f:
                envoy_patch = f.read()
            assert "envoy/source/bar.cc" in envoy_patch
            assert "kubernetes" not in envoy_patch

            # Clean up temp files
            for path in result.values():
                os.unlink(path)
        finally:
            os.unlink(patch_file)

    def test_split_single_repo_only(self):
        """Patch touching only one repo should return only that repo."""
        patch_content = (
            "diff --git a/src/django/django/db/models.py b/src/django/django/db/models.py\n"
            "--- a/src/django/django/db/models.py\n"
            "+++ b/src/django/django/db/models.py\n"
            "@@ -1,1 +1,1 @@\n"
            "-old\n"
            "+new\n"
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".patch", delete=False) as f:
            f.write(patch_content)
            patch_file = f.name

        try:
            result = split_patch_by_repo(
                patch_file, ["django", "tensorflow"]
            )

            assert "django" in result
            assert "tensorflow" not in result

            for path in result.values():
                os.unlink(path)
        finally:
            os.unlink(patch_file)

    def test_split_empty_patch(self):
        """Empty patch should return no repo patches."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".patch", delete=False) as f:
            f.write("")
            patch_file = f.name

        try:
            result = split_patch_by_repo(patch_file, ["kubernetes", "envoy"])
            assert len(result) == 0
        finally:
            os.unlink(patch_file)


class TestValidateCrossRepo:
    """Tests for cross-repo weighted scoring."""

    @mock.patch("validate_patch_cross_repo.run_base_validator")
    def test_two_repo_weighted_scoring(self, mock_validator):
        """Two repos with different weights should produce weighted score."""
        mock_validator.return_value = {"overall_score": 0.8, "task_results": []}

        patch_content = (
            "diff --git a/src/kubernetes/foo.go b/src/kubernetes/foo.go\n"
            "--- a/src/kubernetes/foo.go\n"
            "+++ b/src/kubernetes/foo.go\n"
            "@@ -1,1 +1,1 @@\n"
            "-old\n"
            "+new\n"
            "diff --git a/src/envoy/bar.cc b/src/envoy/bar.cc\n"
            "--- a/src/envoy/bar.cc\n"
            "+++ b/src/envoy/bar.cc\n"
            "@@ -1,1 +1,1 @@\n"
            "-old\n"
            "+new\n"
        )

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".patch", delete=False
        ) as f:
            f.write(patch_content)
            patch_file = f.name

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            output_file = f.name

        try:
            result = validate_cross_repo(
                patch_file,
                {"kubernetes": 0.6, "envoy": 0.4},
                output_file,
                "/fake/corpus",
            )

            # Both repos score 0.8, so weighted = 0.8*0.6 + 0.8*0.4 = 0.8
            assert result["overall_score"] == pytest.approx(0.8, abs=0.01)
            assert "kubernetes" in result["per_repo_scores"]
            assert "envoy" in result["per_repo_scores"]
            assert result["per_repo_scores"]["kubernetes"]["weight"] == 0.6
            assert result["per_repo_scores"]["envoy"]["weight"] == 0.4
        finally:
            os.unlink(patch_file)
            os.unlink(output_file)

    @mock.patch("validate_patch_cross_repo.run_base_validator")
    def test_partial_repo_coverage(self, mock_validator):
        """Patch touching only one of two repos should score proportionally."""
        mock_validator.return_value = {"overall_score": 1.0, "task_results": []}

        # Only kubernetes patch, no envoy
        patch_content = (
            "diff --git a/src/kubernetes/foo.go b/src/kubernetes/foo.go\n"
            "--- a/src/kubernetes/foo.go\n"
            "+++ b/src/kubernetes/foo.go\n"
            "@@ -1,1 +1,1 @@\n"
            "-old\n"
            "+new\n"
        )

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".patch", delete=False
        ) as f:
            f.write(patch_content)
            patch_file = f.name

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            output_file = f.name

        try:
            result = validate_cross_repo(
                patch_file,
                {"kubernetes": 0.6, "envoy": 0.4},
                output_file,
                "/fake/corpus",
            )

            # kubernetes=1.0*0.6=0.6, envoy=0.0*0.4=0.0
            assert result["overall_score"] == pytest.approx(0.6, abs=0.01)
            assert result["per_repo_scores"]["envoy"]["score"] == 0.0
        finally:
            os.unlink(patch_file)
            os.unlink(output_file)

    def test_weight_validation_error(self):
        """Invalid weights should cause exit."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".patch", delete=False
        ) as f:
            f.write("diff --git a/foo b/foo\n")
            patch_file = f.name

        try:
            with pytest.raises(SystemExit):
                validate_cross_repo(
                    patch_file,
                    {"kubernetes": 0.5, "envoy": 0.3},  # sums to 0.8
                    "/dev/null",
                    "/fake/corpus",
                )
        finally:
            os.unlink(patch_file)


class TestSingleRepoFallback:
    """Tests for single-repo (no --weights) behavior."""

    @mock.patch("validate_patch_cross_repo.subprocess.run")
    def test_single_repo_delegates_to_base(self, mock_run):
        """Without --weights, should delegate to base validator."""
        mock_result = mock.MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".patch", delete=False
        ) as f:
            f.write("some patch")
            patch_file = f.name

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as out:
            out.write('{"overall_score": 0.75}')
            output_file = out.name

        try:
            result = run_base_validator(patch_file, output_file, "/some/dir")
            assert result["overall_score"] == 0.75
        finally:
            os.unlink(patch_file)
            os.unlink(output_file)
