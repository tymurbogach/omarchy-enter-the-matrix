-- Bordes y sombra del tema matrix.
--
-- OJO: este fichero SUSTITUYE al que genera omarchy-theme-set-templates desde
-- colors.toml (el bucle de plantillas salta las que ya existen en el tema), asi
-- que los colores van repetidos aqui y hay que mantenerlos a la par con
-- colors.toml. A cambio, es el unico sitio del tema donde se puede fijar el
-- grosor del borde y el redondeo.
--
-- Se carga desde default/hypr/omarchy.lua, o sea ANTES de hypr/looknfeel.lua:
-- lo de aqui son los valores por defecto del tema y el usuario los puede pisar
-- en su looknfeel.lua.

local active_border_color = "rgba(00FF41ff)"
local inactive_border_color = "rgba(11301Caa)"

hl.config({
  general = {
    -- 1 px en vez de 2. A 2 el verde pesaba como una caja pintada alrededor de
    -- cada ventana; a 1 lee como el marco de un terminal, que es lo que se
    -- busca.
    border_size = 1,

    col = {
      active_border = active_border_color,
      inactive_border = inactive_border_color,
    },
  },

  decoration = {
    -- Apenas 2 px: lo justo para que la esquina no sea un angulo recto crudo.
    -- Mas redondeo se iria de genero; cero se veia tosco junto al borde grueso.
    rounding = 2,

    -- Fosforo: un halo verde muy tenue alrededor de la ventana con foco. Es lo
    -- que da el aire CRT sin tocar ni el color ni el grosor del borde. La
    -- inactiva no lleva ninguno, asi que el foco se ve sin subir contrastes.
    shadow = {
      enabled = true,
      range = 14,
      render_power = 3,
      color = "rgba(00FF4130)",
      color_inactive = "rgba(00000000)",
    },
  },

  group = {
    col = {
      border_active = active_border_color,
      border_inactive = inactive_border_color,
    },
  },
})
