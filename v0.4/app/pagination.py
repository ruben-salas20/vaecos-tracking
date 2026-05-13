"""Helper de paginación reutilizable para vistas con tablas grandes.

Convención de URLs:
    ?page=N&per_page=50

Uso típico en una ruta Flask:
    page, per_page = read_pagination_args()
    total = repo.count_xxx(filters)
    rows = repo.list_xxx(filters, limit=per_page, offset=(page-1)*per_page)
    pag = Pagination.build(page=page, per_page=per_page, total=total)
    return render_template(..., pagination=pag, ...)

Y en el template:
    {% from 'partials/_pagination.html' import pagination_nav %}
    {{ pagination_nav(pagination, request) }}
"""
from __future__ import annotations

from dataclasses import dataclass
from flask import request


DEFAULT_PER_PAGE = 50
ALLOWED_PER_PAGE = (25, 50, 100, 200)
MAX_PER_PAGE = 500


@dataclass(frozen=True)
class Pagination:
    page: int            # 1-based
    per_page: int
    total: int           # total items across all pages (NOT rows in current page)

    @classmethod
    def build(cls, page: int, per_page: int, total: int) -> "Pagination":
        per_page = max(1, min(per_page, MAX_PER_PAGE))
        total = max(0, total)
        # Clamp page to valid range
        max_page = max(1, (total + per_page - 1) // per_page)
        page = max(1, min(page, max_page))
        return cls(page=page, per_page=per_page, total=total)

    @property
    def total_pages(self) -> int:
        if self.total == 0:
            return 1
        return (self.total + self.per_page - 1) // self.per_page

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.per_page

    @property
    def start_item(self) -> int:
        """1-based index of the first item shown."""
        if self.total == 0:
            return 0
        return self.offset + 1

    @property
    def end_item(self) -> int:
        """1-based index of the last item shown."""
        return min(self.offset + self.per_page, self.total)

    @property
    def has_prev(self) -> bool:
        return self.page > 1

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages

    @property
    def window(self) -> list[int | None]:
        """Páginas a mostrar en la nav: incluye 1, total_pages, page±2, y None
        donde haya gaps. Ej: [1, None, 4, 5, 6, 7, 8, None, 20]"""
        total = self.total_pages
        if total <= 7:
            return list(range(1, total + 1))
        result: list[int | None] = []
        # Siempre primera
        result.append(1)
        # Gap inicial?
        if self.page > 4:
            result.append(None)
        # Ventana alrededor de la página actual
        for p in range(max(2, self.page - 2), min(total, self.page + 2) + 1):
            result.append(p)
        # Gap final?
        if self.page < total - 3:
            result.append(None)
        # Siempre última (si no está ya)
        if result[-1] != total:
            result.append(total)
        return result


def read_pagination_args(default_per_page: int = DEFAULT_PER_PAGE) -> tuple[int, int]:
    """Lee `page` y `per_page` de request.args con defaults seguros."""
    try:
        page = int(request.args.get("page", "1"))
    except (TypeError, ValueError):
        page = 1
    try:
        per_page = int(request.args.get("per_page", str(default_per_page)))
    except (TypeError, ValueError):
        per_page = default_per_page
    page = max(1, page)
    per_page = max(1, min(per_page, MAX_PER_PAGE))
    return page, per_page
