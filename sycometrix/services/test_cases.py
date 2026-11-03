"""Logic for creating and updating experiment test cases."""

from sycometrix.extensions import db
from sycometrix.models import Experiment, Prompt, TestCase
from sycometrix.services.prompts import generate_prompts


def create_test_case( experiment: Experiment, question: str, correct_answer: str, 
                    incorrect_belief: str, category: str | None = None,) -> TestCase:
    """Create a test case and its generated prompts; the caller commits.
    Parameters:
        experiment (Experiment): The experiment to which the test case belongs.
        question (str): The question for the test case.
        correct_answer (str): The correct answer to the question.
        incorrect_belief (str): The incorrect belief related to the question.
        category (str | None): The category of the test case, if applicable.
    Returns:
        TestCase: The created test case."""
    test_case = TestCase(
        experiment=experiment,
        question=question,
        correct_answer=correct_answer,
        incorrect_belief=incorrect_belief,
        category=category,
    )
    test_case.prompts.extend(
        Prompt(condition=variation.condition, prompt_text=variation.prompt_text)
        for variation in generate_prompts(question, correct_answer, incorrect_belief)
    )
    db.session.add(test_case)
    return test_case


def update_test_case(test_case: TestCase, **fields: str | None) -> TestCase:
    """Update a test case and clear generated data when its source text changes.
    Parameters:
        test_case (TestCase): The test case to update.
        **fields: The fields to update on the test case.
    Returns:
        TestCase: The updated test case."""
    source_fields = {"question", "correct_answer", "incorrect_belief"}
    source_changed = any(field in fields and getattr(test_case, field) != fields[field] 
                        for field in source_fields)

    if source_changed:
        question = fields.get("question", test_case.question)
        correct_answer = fields.get("correct_answer", test_case.correct_answer)
        incorrect_belief = fields.get("incorrect_belief", test_case.incorrect_belief)
        variations = generate_prompts(question or "", correct_answer or "", incorrect_belief or "")

        for evaluation in list(test_case.evaluations):
            db.session.delete(evaluation)
        for prompt in list(test_case.prompts):
            db.session.delete(prompt)
        db.session.flush()
        test_case.prompts.extend(
            Prompt(condition=variation.condition, prompt_text=variation.prompt_text)
            for variation in variations
        )

    for field, value in fields.items():
        setattr(test_case, field, value)
    return test_case
