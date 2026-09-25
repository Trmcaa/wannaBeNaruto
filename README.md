## Shinobi Generátor

Pygame hra používá standardní `src` layout:

- `src/shinobi_generator/config/settings.py` obsahuje Pygame konfiguraci, layout, barvy a fonty.
- `src/shinobi_generator/ui/render.py` obsahuje společné kreslicí utility.
- `src/shinobi_generator/core/game.py` obsahuje herní stav, pravidla a herní obrazovky.
- `src/shinobi_generator/app/main.py` obsahuje aplikační smyčku Pygame.
- `src/shinobi_generator/__main__.py` umožňuje spuštění balíčku jako modulu.
- `naruto.py` zůstává kompatibilním spouštěcím wrapperem.

Spuštění:

```bash
pip install pygame
python3 naruto.py
```

Alternativně:

```bash
PYTHONPATH=src python3 -m shinobi_generator
```
