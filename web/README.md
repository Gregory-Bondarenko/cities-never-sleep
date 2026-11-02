# web/: витрина

Одна страница `src/index.html`: трёхмерная сцена на three.js, сюжет по прокрутке, поиск и карточка города. Устройство и причины выбора описаны в [ADR-0009](../docs/adr/0009-web-without-bundler.md).

Витрина только читает выгрузки из `analytics/exports/` и ничего не пересчитывает ([ADR-0001](../docs/adr/0001-analytics-artifacts-web.md)). Цифры в тексте страницы сверяет тест `tests/test_web_copy.py`.

```bash
python3 web/build.py                       # страница и данные в web/dist
python3 -m http.server -d web/dist 8000    # просмотр: http://localhost:8000
```

Публикация на GitHub Pages идёт автоматически из `main` (workflow `pages`).
