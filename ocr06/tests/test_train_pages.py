"""Testes das partes puras do treino de páginas (pesos por trecho, currículo, perda).
O teste com o tokenizer real e um modelo minúsculo é scripts/check_train_pages.py.

    .venv-cputest/bin/python -m pytest tests/test_train_pages.py -q
"""
import pytest

torch = pytest.importorskip("torch")
from ocr06.model import train as T  # noqa: E402


def test_token_weights_spans_default_mask_and_end():
    # conteúdo "<p>Ana</p><p>X</p>" + "<|im_end|>\n"; trechos: Ana (w=1), X (w=0)
    content = "<p>Ana</p><p>X</p>"
    offs = [(0, 3), (3, 4), (4, 6), (6, 10), (10, 13), (13, 14), (14, 18), (18, 28), (28, 29)]
    spans = [{"start": 3, "end": 6, "w": 1.0}, {"start": 13, "end": 14, "w": 0.0}]
    w = T.token_weights(offs, len(content), 0, spans, 0.3)
    assert w == [0.3, 1.0, 1.0, 0.3, 0.3, 0.0, 0.3, 1.0, 1.0]


def test_token_weights_boundary_token_takes_smallest_span_and_trim_shift():
    # token que toca dois trechos fica com o menor peso; shift desfaz o trim do template
    spans = [{"start": 2, "end": 4, "w": 1.0}, {"start": 4, "end": 6, "w": 0.0}]
    assert T.token_weights([(1, 3)], 10, 2, spans, 0.3) == [0.0]
    assert T.token_weights([(0, 1)], 10, 2, spans, 0.3) == [1.0]


def test_curriculum_order_levels_ascending_lines_interleaved():
    rows = [{"level": lv} for lv in (3, 1, 4, 2, 1, 2)] + [{"id": "l1"}, {"id": "l2"}]
    order = T.curriculum_order(rows, 0)
    levels = [rows[i].get("level") for i in order]
    assert [lv for lv in levels if lv is not None] == [1, 1, 2, 2, 3, 4]
    assert levels[0] is not None and levels[-1] is not None and None in levels[1:4] and None in levels[4:7]
    assert order == T.curriculum_order(rows, 0) and sorted(order) == list(range(8))
    s = T.CurriculumSampler(rows, 0)
    assert list(s) == order and len(s) == 8
    s.set_epoch(1)
    assert sorted(s) == list(range(8))


def test_weighted_loss_matches_mean_ce_with_unit_weights_and_ignores_zero_weight():
    torch.manual_seed(0)
    logits = torch.randn(2, 6, 11)
    labels = torch.tensor([[-100, -100, 3, 4, 5, 6], [-100, -100, 2, 3, -100, -100]])
    ones = (labels != -100).float()
    ref = torch.nn.functional.cross_entropy(logits[:, :-1].reshape(-1, 11), labels[:, 1:].reshape(-1),
                                            ignore_index=-100)
    assert torch.allclose(T.weighted_lm_loss(logits, labels, ones), ref)
    # 1º alvo na posição 2: bastam as últimas 6 - 2 + 1 = 5 posições (logits_to_keep)
    assert torch.allclose(T.weighted_lm_loss(logits[:, 1:], labels, ones), ref)
    w = ones.clone()
    w[0, 5] = 0.0
    keep = labels.clone()
    keep[0, 5] = -100
    ref2 = torch.nn.functional.cross_entropy(logits[:, :-1].reshape(-1, 11), keep[:, 1:].reshape(-1),
                                             ignore_index=-100)
    assert torch.allclose(T.weighted_lm_loss(logits, labels, w), ref2)


def test_is_page():
    assert T.is_page({"spans": []}) and T.is_page({"w_default": 0.3})
    assert not T.is_page({"text": "Ana", "source": "bressay"})
