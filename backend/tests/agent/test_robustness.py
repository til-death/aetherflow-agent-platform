from app.agent.evaluation import load_benchmark_tasks
from app.agent.robustness import evaluate_robustness, perturb_task


def test_perturbation_is_reproducible_and_keeps_expected_labels() -> None:
    task = load_benchmark_tasks("sample")[0]

    first = perturb_task(task, seed=19, variant="bilingual")
    second = perturb_task(task, seed=19, variant="bilingual")

    assert first == second
    assert first.id != task.id
    assert first.expected_scenario == task.expected_scenario
    assert first.expected_tool == task.expected_tool


def test_robustness_report_contains_baseline_stress_and_negative_controls() -> None:
    report = evaluate_robustness(dataset="sample", seeds=(7,), variants=("bilingual", "sparse_input"))

    assert report["baseline"]["case_count"] == 10
    assert report["stress"]["case_count"] == 20
    assert report["by_seed"]["7"]["case_count"] == 20
    assert all(control["detected_failure"] for control in report["negative_controls"])
