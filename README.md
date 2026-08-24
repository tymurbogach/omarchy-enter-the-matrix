# Matrix — tema para Omarchy

Verde fósforo sobre negro, con lluvia digital. Fondos, splash de arranque y una
paleta pensada para que el código siga siendo legible, no solo bonito.

![vista previa](preview.png)

## Instalar

```bash
omarchy theme install https://github.com/tymurbogach/omarchy-matrix-theme
```

Eso deja el tema en `~/.config/omarchy/themes/matrix` y lo aplica.

### Lluvia animada (opcional)

Salvapantallas, bloqueo y fondo de escritorio lloviendo, no imágenes fijas:

```bash
~/.config/omarchy/themes/matrix/lluvia/instalar.sh
```

Las tres funcionan distinto y ninguna se configura, así que el script toca las
tres por separado:

| | |
|---|---|
| **Salvapantallas** | Es `ttfx` dentro de un terminal, y `omarchy-launch-screensaver` lo llama por nombre. El script deriva un clon del que tengas instalado cambiando `--random-effect` por `matrix --rain-time 86400`, y antepone `~/.local/bin` en el PATH desde `hypr/autostart.lua`. Después: `hyprctl reload && omarchy restart shell`. |
| **Bloqueo** | Llueve siempre, con el fondo que sea. Compruébalo sin bloquearte con `omarchy-shell lock preview`. |
| **Fondo** | Elige `0-lluvia-viva.png` en el carrusel. Con cargador llueve siempre; con batería, solo mientras no haya ventanas en el espacio de trabajo. |

El clon del salvapantallas se **deriva** del tuyo, no viene empaquetado: así
hereda los arreglos de tu versión de Omarchy. Los plugins no se puede: van
enteros, y un plugin clonado **queda congelado** — deja de recibir lo que
Omarchy arregle en `lock` o `background`.

La prioridad de PATH va en `hypr/autostart.lua` y no en `uwsm/env.d/`, aunque sea
donde parece que toca: `default/hypr/envs.lua` vuelve a anteponer
`$OMARCHY_PATH/bin` en cada arranque de Hyprland **y en cada `hyprctl reload`**,
así que pisa cualquier cosa que haya puesto uwsm. `autostart.lua` se carga
después de esos defaults.

> **`omarchy refresh shell` apaga la lluvia.** Ese comando resetea
> `~/.config/omarchy/shell.json`, que es donde se guarda qué plugins están
> activos, así que los clones quedan desactivados y vuelven el bloqueo y el fondo
> de serie. No se rompe nada: se recupera volviendo a correr `instalar.sh`, o con
> `omarchy plugin enable $USER.lock && omarchy plugin enable $USER.background`.
> Como el fondo estático es un fotograma del propio shader, el síntoma parece una
> lluvia congelada y no un plugin apagado.

Para deshacerlo:

```bash
omarchy plugin remove $USER.lock
omarchy plugin remove $USER.background
rm ~/.local/bin/omarchy-screensaver
```

### Splash de arranque (opcional)

```bash
omarchy plymouth set matrix
```

## Qué lleva dentro

| | |
|---|---|
| `colors.toml` | La paleta. Semántica, no `color0..15`. |
| `shell.{bar,menu,launcher,notifications}.toml` | Overrides de sección de la shell: dan relieve a barra y tarjetas, que si no pintan todas del mismo negro. |
| `backgrounds/` | El fotograma del fondo vivo, a 3840×2400. Sirve de miniatura en el carrusel y de marcador: al elegirlo se enciende la lluvia animada. |
| `unlock.png`, `preview-unlock.png` | Marca del splash de Plymouth. |
| `lluvia/` | La lluvia animada: shader, atlas de glifos, los QML de los dos plugins y el instalador. |
| `generar-fondos.py`, `generar-marca.py` | Regeneran los PNG. Ninguno es un binario intocable. |

### La paleta

Todo es verde salvo el rojo, que se reserva para errores. Lo que la separa de
un tema verde cualquiera es que cada slot ANSI ocupa un **peldaño distinto de
luminosidad**, así que en `nvim` o `bat` los roles sintácticos se distinguen en
vez de fundirse en una mancha. Contraste mínimo contra el fondo: 4.86.

| | | |
|---|---|---|
| `yellow` | `#C6FF57` | lima · 17.1 |
| `cyan` | `#7BFFD4` | menta · 16.4 |
| `green` | `#00FF41` | el héroe · 14.8 |
| `orange` | `#8FE03A` | · 12.4 |
| `magenta` | `#35D68F` | jade · 10.7 |
| `blue` | `#12A96A` | esmeralda · 6.6 |
| `red` | `#F0263F` | errores · 4.9 |

### Regenerar los PNG

```bash
./generar-fondos.py                 # los cuatro fondos
./generar-fondos.py --out /tmp/x.png --seed 42 --density 0.7
./generar-marca.py                  # unlock, preview-unlock y preview
./lluvia/generar-atlas.py           # el atlas de glifos del shader
```

Hace falta ImageMagick, `rsvg-convert`, Python 3 y la fuente Noto Sans CJK JP.

## Créditos

El shader de lluvia parte de [`matrix.frag` de
bjarneo/quickshell](https://github.com/bjarneo/quickshell) (MIT). Cambia los
bloques procedurales del original por un atlas con los katakana de media
anchura reales — que son exactamente los de `ttfx matrix`, el efecto del
screensaver de Omarchy — y usa sus mismos colores.

## Licencia

MIT.
