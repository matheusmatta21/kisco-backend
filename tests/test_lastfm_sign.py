"""
Testes unitários da função _sign do lastfm_adapter.

Valida:
  1. Vetor âncora — string concatenada conhecida → hash MD5 conhecido.
  2. Ordenação alfabética — ordem de inserção dos params não afeta o resultado.
  3. Exclusão de format/callback — esses params não entram no hash.
  4. Determinismo — mesmo input gera mesmo output.
  5. Sensibilidade — qualquer mudança de param/secret muda o hash.
  6. UTF-8 — params com acento não quebram.

Uso:
    uv run python tests/test_lastfm_sign.py
"""
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import lastfm_adapter
from app.config import settings


def _md5(s: str) -> str:
    return hashlib.md5(s.encode("utf-8")).hexdigest()


def main() -> None:
    original_secret = settings.LASTFM_SHARED_SECRET
    settings.LASTFM_SHARED_SECRET = "mysecret"

    try:
        # 1. Vetor âncora — recalcula o MD5 manualmente e compara
        params = {
            "method": "auth.getSession",
            "api_key": "abc123",
            "token": "xyz789",
        }
        expected_string = "api_keyabc123methodauth.getSessiontokenxyz789mysecret"
        expected_hash = _md5(expected_string)
        actual = lastfm_adapter._sign(params)
        assert actual == expected_hash, f"esperado {expected_hash}, veio {actual}"
        print(f"[1] vetor ancora: OK ({actual})")

        # 2. Ordenação alfabética — ordem dos params não importa
        params_a = {"api_key": "abc123", "method": "auth.getSession", "token": "xyz789"}
        params_b = {"token": "xyz789", "method": "auth.getSession", "api_key": "abc123"}
        sig_a = lastfm_adapter._sign(params_a)
        sig_b = lastfm_adapter._sign(params_b)
        assert sig_a == sig_b, f"sigs deveriam ser iguais, mas {sig_a} != {sig_b}"
        print(f"[2] ordem dos params nao afeta hash: OK")

        # 3. format e callback nao entram no hash
        params_clean = {"method": "auth.getSession", "api_key": "abc123", "token": "xyz789"}
        params_with_format = {**params_clean, "format": "json", "callback": "http://x"}
        sig_clean = lastfm_adapter._sign(params_clean)
        sig_with = lastfm_adapter._sign(params_with_format)
        assert sig_clean == sig_with, "format/callback nao deveriam afetar a assinatura"
        print(f"[3] format e callback ignorados: OK")

        # 4. Determinismo — chamar de novo da o mesmo resultado
        sig_again = lastfm_adapter._sign(params_clean)
        assert sig_again == sig_clean, "funcao deveria ser deterministica"
        print(f"[4] deterministico: OK")

        # 5. Mudar um param muda o hash
        params_diff = {**params_clean, "token": "different"}
        sig_diff = lastfm_adapter._sign(params_diff)
        assert sig_diff != sig_clean, "mudar um param deveria mudar o hash"
        print(f"[5] sensibilidade a mudanca de param: OK")

        # 5b. Mudar o secret muda o hash
        settings.LASTFM_SHARED_SECRET = "outro_secret"
        sig_other_secret = lastfm_adapter._sign(params_clean)
        settings.LASTFM_SHARED_SECRET = "mysecret"
        assert sig_other_secret != sig_clean, "mudar o secret deveria mudar o hash"
        print(f"[5b] sensibilidade a mudanca de secret: OK")

        # 6. UTF-8 — acentos nao quebram
        params_utf8 = {"method": "user.getInfo", "user": "joão", "api_key": "abc"}
        sig_utf8 = lastfm_adapter._sign(params_utf8)
        expected_utf8 = _md5("api_keyabcmethoduser.getInfouserjoãomysecret")
        assert sig_utf8 == expected_utf8, f"UTF-8: esperado {expected_utf8}, veio {sig_utf8}"
        print(f"[6] UTF-8 com acento: OK ({sig_utf8})")

        print("\nTodos os 6 testes passaram.")
    finally:
        settings.LASTFM_SHARED_SECRET = original_secret


if __name__ == "__main__":
    main()
