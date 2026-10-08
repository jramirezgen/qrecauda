-- Filtro de pandoc (2.9) para paper.md. No cambia el contenido: sólo presentación.
--   1. «⚠️» pasa al símbolo \warnsym (triángulo con «!», color bermellón de la paleta Okabe-Ito).
--   2. Referencias cruzadas: [Figura](#fig:id), [Tabla](#tbl:id), [§](#sec:id) se resuelven a «Figura 3», «Tabla 2», «§4.1».
--      Si el texto del enlace es «N» sólo se escribe el número. Una tabla se ancla con un span en su pie: `[]{#tbl:id}`.
--   3. Tablas: cabecera en negrita y cuerpo en \small (booktabs ya lo pone pandoc).
--   4. Div .refs: lista de referencias con sangría francesa.
local FIG, TBL, SEC = {}, {}, {}

local function texto(inls) return pandoc.utils.stringify(inls) end

-- ── pasada 1: numerar ──────────────────────────────────────────────────────────────────────
local function numerar(doc)
  local nf, nt = 0, 0
  local cs = {0, 0, 0}
  pandoc.walk_block(pandoc.Div(doc.blocks), {
    Header = function(h)
      if h.classes:includes("unnumbered") or h.level > 3 then return nil end
      cs[h.level] = cs[h.level] + 1
      for i = h.level + 1, 3 do cs[i] = 0 end
      local partes = {}
      for i = 1, h.level do partes[#partes + 1] = tostring(cs[i]) end
      if h.identifier ~= "" then SEC[h.identifier] = table.concat(partes, ".") end
      return nil
    end,
    Image = function(im)
      if im.identifier ~= "" and im.identifier:sub(1, 4) == "fig:" then
        nf = nf + 1
        FIG[im.identifier] = tostring(nf)
      end
      return nil
    end,
    Table = function(t)
      local cap = t.caption
      pandoc.walk_block(pandoc.Para(cap), {
        Span = function(s)
          if s.identifier ~= "" and s.identifier:sub(1, 4) == "tbl:" then
            nt = nt + 1
            TBL[s.identifier] = tostring(nt)
          end
          return nil
        end
      })
      return nil
    end,
  })
end

-- ── pasada 2: reescribir ───────────────────────────────────────────────────────────────────
local function enlace(l)
  local id = l.target:match("^#(.+)$")
  if not id then return nil end
  local tabla, etiqueta
  if id:sub(1, 4) == "fig:" then tabla, etiqueta = FIG, "Figura"
  elseif id:sub(1, 4) == "tbl:" then tabla, etiqueta = TBL, "Tabla"
  elseif id:sub(1, 4) == "sec:" then tabla, etiqueta = SEC, "§"
  else return nil end
  local n = tabla[id]
  if not n then
    io.stderr:write("filtro.lua: referencia sin destino: " .. id .. "\n")
    return pandoc.Strong({pandoc.Str("??" .. id)})
  end
  local t = texto(l.content)
  local rotulo
  if t == "N" then rotulo = n else rotulo = t .. "\u{00A0}" .. n end
  return pandoc.Link({pandoc.Str(rotulo)}, l.target, l.title, l.attr)
end

local function aviso(s)
  if not s.text:find("⚠") then return nil end
  local salida, resto = {}, s.text
  while true do
    local i, j = resto:find("⚠")
    if not i then break end
    if i > 1 then salida[#salida + 1] = pandoc.Str(resto:sub(1, i - 1)) end
    salida[#salida + 1] = pandoc.RawInline("latex", "\\warnsym{}")
    resto = resto:sub(j + 1)
  end
  if #resto > 0 then salida[#salida + 1] = pandoc.Str(resto) end
  return salida
end

local function tabla(t)
  local nuevas = {}
  for i, celda in ipairs(t.headers) do
    local bloques = {}
    for _, b in ipairs(celda) do
      if b.t == "Plain" or b.t == "Para" then
        bloques[#bloques + 1] = pandoc.Plain({pandoc.Strong(b.content)})
      else bloques[#bloques + 1] = b end
    end
    nuevas[i] = bloques
  end
  t.headers = nuevas
  return {pandoc.RawBlock("latex", "\\begingroup\\small"), t, pandoc.RawBlock("latex", "\\endgroup")}
end

local function refs(d)
  if d.classes:includes("refs") then
    local out = {pandoc.RawBlock("latex", "\\begin{referencias}")}
    for _, b in ipairs(d.content) do out[#out + 1] = b end
    out[#out + 1] = pandoc.RawBlock("latex", "\\end{referencias}")
    return out
  end
  return nil
end

return {
  { Pandoc = function(doc) numerar(doc); return nil end },
  { Link = enlace, Str = aviso, Table = tabla, Div = refs },
}
