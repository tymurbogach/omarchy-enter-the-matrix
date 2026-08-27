# Matrix — pack para Omarchy 4

Verde fósforo sobre negro. Un tema normal de Omarchy y, encima, la misma lluvia
digital en el escritorio, en el salvapantallas y al bloquear.

![vista previa](preview.png)

## Instalar

**El tema.** Colores, fondos y splash de arranque. No depende de nada más:

```bash
omarchy theme install https://github.com/tymurbogach/omarchy-matrix
omarchy theme set matrix
```

**La lluvia.** Es un plugin de la shell y va aparte, porque una animación no
cabe dentro de un tema de Omarchy:

```bash
~/.config/omarchy/themes/matrix/instalar.sh
```

La lluvia de escritorio es un fondo más del carrusel, `0-lluvia-viva`.
`omarchy-matrix wallpaper on` lo selecciona por ti. Ojo: `omarchy theme set` rota
al siguiente fondo del tema, así que reaplicar el tema te saca de la lluvia —
vuelve con ese mismo comando o desde el menú.

## Las piezas

Cada una se enciende y se apaga por separado, desde el menú
(**SUPER → Style → Matrix**, con ✓) o desde la línea de comandos:

```bash
omarchy-matrix status
omarchy-matrix wallpaper off
omarchy-matrix boot on
```

| Pieza | Qué es | Cómo está hecha |
|---|---|---|
| `wallpaper` | La lluvia de fondo de escritorio | Capa propia del plugin en `WlrLayer.Bottom`: por encima del fondo, por debajo de toda ventana, con `mask: Region {}` para que los clics lleguen al escritorio. **El fondo de Omarchy no se toca.** Se ve al tener elegido el fondo `0-lluvia-viva`. Con cargador llueve siempre; con batería, solo mientras no haya ventanas en el espacio activo. |
| `screensaver` | La lluvia al quedarte quieto | La misma capa en `WlrLayer.Overlay`, con el tiempo de `idle.screensaver` de tu `shell.json`. Pone el flag nativo `screensaver-off` para que Omarchy no abra además su salvapantallas en terminal. |
| `lock` | La lluvia al bloquear | Lo único que sustituye un plugin de Omarchy. Ver abajo. |
| `boot` | La imagen de antes del login | `omarchy plymouth set-by-theme matrix`, que ya es nativo. Pide contraseña, así que nunca se aplica solo. |

Los tres primeros son **el mismo shader**, instanciado tres veces. Eso es a
propósito: antes el salvapantallas era `ttfx` dentro de un terminal —otro
programa dibujando otra lluvia— y no había manera de que los tres cuadrasen.

## El lock

Una `WlSessionLock` es exclusiva por protocolo: nada puede dibujar dentro de su
superficie salvo ella misma. Así que para llover ahí hay que sustituir el plugin
del bloqueo, y no hay otra.

Lo que **no** se hace es publicar una copia congelada. Dentro de ese plugin están
los flujos de PAM y de huella, y la última copia que quieres es una vieja.
`bin/derivar-lock.py` parte siempre del `LockView.qml` de **tu** Omarchy y le
aplica un cambio mínimo: quita el wallpaper desenfocado y pone la lluvia. Las
otras ~200 líneas son las tuyas. Un hook `post-update.d` lo vuelve a derivar
después de cada `omarchy update`, así que los arreglos de Omarchy siguen
llegando.

Si el bloque a sustituir no aparece exactamente una vez, el script **aborta y te
lo dice** en vez de dejarlo a medias.

Pruébalo sin bloquearte: `omarchy-shell lock preview`. Para volver al de
Omarchy: `omarchy-matrix lock off`.

## Qué se toca de tu sistema

Todo lo que instala el pack son archivos suyos o archivos que Omarchy deja para
extender. **Nada** de `/usr/share/omarchy/`, ni `hyprland.lua`, ni el fondo, ni
la barra:

```
~/.config/omarchy/plugins/matrix.rain/     el plugin
~/.config/omarchy/matrix.json              qué piezas están encendidas
~/.config/omarchy/hooks/{theme-set,post-update}.d/matrix
~/.config/omarchy/extensions/omarchy-menu.jsonc   (bloque entre marcas)
~/.local/bin/{omarchy-matrix,derivar-lock.py}
~/.config/omarchy/plugins/<usuario>.lock   solo si `lock` está encendido
```

`./desinstalar.sh` lo quita todo y deja el tema funcionando como cualquier otro.

> **`omarchy refresh shell` apaga la lluvia.** Ese comando reescribe
> `shell.json` entero, y ahí es donde Omarchy guarda qué plugins están activos.
> No hay hook posterior al que engancharse. Se recupera con `omarchy-matrix
> doctor`, o volviendo a aplicar el tema — el hook de `theme-set` lo hace solo.

## Automático

| Cuándo | Qué pasa |
|---|---|
| `omarchy theme set matrix` | Se enciende lo que tuvieras encendido |
| `omarchy theme set <otro>` | El pack se aparta sin olvidar tus ajustes |
| `omarchy update` | Se vuelve a derivar el lock del recién actualizado |

Apartarse quiere decir: el plugin se desactiva, vuelve el salvapantallas de
Omarchy y **se borra el clon del lock** — con `omarchy plugin remove`, que es
quien reactiva el de Omarchy; desactivarlo a secas te dejaría sin ningún lock
habilitado. Tus ajustes no se tocan: al volver a matrix vuelve exactamente lo que
tenías.

`boot` es la excepción y no se aparta: el splash de Plymouth es del sistema, no
del tema.

Mientras el pack está apartado, el menú **no marca nada** y `omarchy-matrix
status` dice por qué. El ✓ significa "esto está pasando ahora", no "lo tienes
configurado".

## Qué lleva dentro

| | |
|---|---|
| `colors.toml` | La paleta. Semántica, no `color0..15`. Incluye los colores del borde de Hyprland, que van por plantilla. |
| `shell.{bar,menu,launcher,notifications}.toml` | Overrides de sección de la shell: dan relieve a barra y tarjetas, que si no pintan todas del mismo negro. |
| `backgrounds/` | Los fondos, a 3840×2400. `0-lluvia-viva` es un fotograma del propio shader: sirve de miniatura, de marcador y de respaldo. |
| `unlock.png`, `preview-unlock.png` | Marca del splash de Plymouth. |
| `manifest.json`, `Service.qml`, `MatrixRain.qml`, `matrix.frag.qsb`, `glifos.png` | El plugin. |
| `bin/`, `hooks/`, `extensions/` | El CLI, la auto-reparación y las entradas de menú. |
| `lluvia/` | Las fuentes del shader: `matrix.frag` y el generador del atlas. |
| `generar-fondos.py`, `generar-marca.py` | Regeneran los PNG. Ninguno es un binario intocable. |

### Sobre los bordes

El tema fija el **color** del borde (`hyprland_active_border`, verde plano) pero no
su grosor ni el redondeo: `omarchy theme install` **rechaza cualquier `.lua`** de
un tema clonado de git, porque Lua corre código dentro del compositor. Es una
decisión de Omarchy, no un fallo. Los bordes quedan con el grosor de fábrica.

Si quieres el marco fino, es tu `~/.config/hypr/looknfeel.lua`:

```lua
hl.config({
  general = { border_size = 1 },
  decoration = {
    rounding = 2,
    shadow = { enabled = true, range = 14, color = "rgba(00FF4130)",
               color_inactive = "rgba(00000000)" },
  },
})
```

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

### Regenerar

```bash
./generar-fondos.py                 # los fondos
./generar-fondos.py --out /tmp/x.png --seed 42 --density 0.7
./generar-marca.py                  # unlock, preview-unlock y preview
./lluvia/generar-atlas.py           # el atlas de glifos del shader
qsb --glsl 100es,120,150 --hlsl 50 --msl 12 \
    -o matrix.frag.qsb lluvia/matrix.frag    # recompilar el shader
```

Hace falta ImageMagick, `rsvg-convert`, Python 3, la fuente Noto Sans CJK JP y
`qt6-shadertools` para `qsb`.

## Créditos

El shader de lluvia parte de [`matrix.frag` de
bjarneo/quickshell](https://github.com/bjarneo/quickshell) (MIT). Cambia los
bloques procedurales del original por un atlas con los katakana de media
anchura reales — que son exactamente los de `ttfx matrix`, el efecto del
screensaver de Omarchy — y usa sus mismos colores.

## Licencia

MIT.
