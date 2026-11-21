"""Błędy domenowe: serwisy rzucają `DomainError`, `create_app` zamienia je na odpowiedź HTTP.

`detail` jest zawsze po polsku i trafia do użytkownika.
"""


class DomainError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail
