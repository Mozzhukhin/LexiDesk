from pathlib import Path

from lexidesk.answers import AnswerGrade, evaluate_answer, normalize_answer
from lexidesk.database import WordRepository


def test_answer_evaluation_accepts_alternatives_and_small_typos(
    tmp_path: Path,
) -> None:
    repository = WordRepository(tmp_path / "answers.db")
    word_id = repository.add_word(
        source_text="opportunity",
        source_lang="en",
        target_text="возможность",
        alternatives=["шанс"],
    )
    word = repository.get_word(word_id)
    assert evaluate_answer("  ВОЗМО́ЖНОСТЬ! ", word).grade == AnswerGrade.CORRECT
    assert evaluate_answer("шанс", word).grade == AnswerGrade.CORRECT
    close = evaluate_answer("возможност", word)
    assert close.grade == AnswerGrade.CLOSE
    assert close.suggested_rating == "hard"
    assert evaluate_answer("случай", word).grade == AnswerGrade.WRONG
    repository.close()


def test_answer_normalization_removes_stress_and_punctuation() -> None:
    assert normalize_answer("Предложе́ние!") == "предложение"
