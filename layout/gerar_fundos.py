"""Desenha os fundos das 3 páginas do relatório no PowerPoint e exporta os PNGs.

Uso:  python layout/gerar_fundos.py   (Windows com PowerPoint instalado e pywin32)
Saída: layout/layout_paginas.pptx (editável à mão) e layout/fundo_<pagina>.png (1920x1080).

As posições estão em pixels do relatório (1280x720), as mesmas usadas nos visual.json,
para os visuais do Power BI caírem certinho dentro dos quadros desenhados aqui.
"""
from pathlib import Path

import win32com.client

PASTA = Path(__file__).resolve().parent
PX = 0.75   # 1 px do relatório (1280 de largura) = 0,75 pt no slide (960 pt)

# Paleta (a mesma do tema PrumoPetroleo.json)
FUNDO_1, FUNDO_2 = "#0E2A31", "#081A1F"
LATERAL = "#06161A"
DESTAQUE_1, DESTAQUE_2 = "#1B4A54", "#0F2F37"
AMBAR = "#F59E0B"
TEAL = "#1F7A8C"
BRANCO = "#FFFFFF"
TEXTO_2 = "#9FB3B8"
MENU = "#C9D8DB"
RODAPE = "#6E868C"

PAGINAS = {
    "resultado": {"menu": "Resultado", "titulo": "RESULTADO (DRE)",
                  "subtitulo": "A Prumo cresce e dá lucro, mas a margem encolhe",
                  "principal": "DRE dos três anos (R$ mil e % da receita líquida)",
                  "segundo": "Realizado x orçado por grupo (100% = orçado)"},
    "caixa": {"menu": "Caixa", "titulo": "CAIXA",
              "subtitulo": "O lucro não vira caixa: o dinheiro fica com os clientes",
              "principal": "Lucro líquido x geração de caixa por mês",
              "segundo": "Para onde foi o dinheiro no ano"},
    "capitalGiro": {"menu": "Capital de giro", "titulo": "CAPITAL DE GIRO",
                    "subtitulo": "Mais prazo para vender mais, e quem paga pior entrou junto",
                    "principal": "Prazo de recebimento (PMR) x prazo de pagamento (PMP), em dias",
                    "segundo": "Carteira a receber por faixa de atraso"},
}
MENU_Y = [250, 298, 346]
CARTOES_X = [214, 478, 742, 1006]                 # 4 cartões de 248 x 80, em y 96
DESTAQUE = (214, 192, 360, 248)
SEGUNDO = (214, 456, 360, 244)
PRINCIPAL = (590, 192, 666, 508)


def rgb(cor):
    r, g, b = int(cor[1:3], 16), int(cor[3:5], 16), int(cor[5:7], 16)
    return r + g * 256 + b * 65536   # o PowerPoint guarda as cores como BGR


def forma(slide, nome, x, y, w, h, cor, raio=0, transparencia=0.0, borda=None, tipo=None):
    tipo = tipo or (5 if raio else 1)   # 5 = retângulo arredondado, 1 = retângulo, 9 = elipse
    s = slide.Shapes.AddShape(tipo, x * PX, y * PX, w * PX, h * PX)
    s.Name = nome
    s.Fill.ForeColor.RGB = rgb(cor)
    s.Fill.Transparency = transparencia
    s.Shadow.Visible = False
    if raio:
        s.Adjustments.SetItem(1, raio / min(w, h))   # raio do canto, em fração do lado menor
    if borda:
        s.Line.ForeColor.RGB = rgb(borda[0])
        s.Line.Transparency = borda[1]
        s.Line.Weight = 0.75
    else:
        s.Line.Visible = False
    return s


def degrade(s, cor_1, cor_2, estilo=4):
    s.Fill.TwoColorGradient(estilo, 1)   # 4 = diagonal descendo, 1 = de cima para baixo
    s.Fill.ForeColor.RGB = rgb(cor_1)
    s.Fill.BackColor.RGB = rgb(cor_2)


def texto(slide, nome, x, y, w, h, conteudo, tamanho, cor, fonte="Segoe UI", negrito=False):
    s = slide.Shapes.AddTextbox(1, x * PX, y * PX, w * PX, h * PX)
    s.Name = nome
    tf = s.TextFrame
    tf.MarginLeft = tf.MarginRight = tf.MarginTop = tf.MarginBottom = 0
    tf.WordWrap = True
    tf.AutoSize = 0
    tr = tf.TextRange
    tr.Text = conteudo
    tr.Font.Name = fonte
    tr.Font.Size = tamanho * PX
    tr.Font.Bold = negrito
    tr.Font.Color.RGB = rgb(cor)
    return s


def vidro(slide, nome, x, y, w, h, raio=16):
    return forma(slide, nome, x, y, w, h, BRANCO, raio=raio, transparencia=0.94, borda=(BRANCO, 0.88))


def desenhar(slide, chave, pagina):
    # fundo com degradê e dois brilhos suaves
    degrade(forma(slide, "fundo", 0, 0, 1280, 720, FUNDO_1), FUNDO_1, FUNDO_2)
    for nome, (x, y, w, h), cor, transp in (("brilho_ambar", (880, 430, 560, 460), AMBAR, 0.92),
                                            ("brilho_teal", (300, -260, 620, 460), TEAL, 0.80)):
        b = forma(slide, nome, x, y, w, h, cor, transparencia=transp, tipo=9)
        b.SoftEdge.Radius = 100

    # barra lateral: marca em texto, menu e rodapé
    forma(slide, "lateral", 0, 0, 190, 720, LATERAL, transparencia=0.25)
    forma(slide, "lateral_divisa", 190, 0, 1, 720, BRANCO, transparencia=0.9)
    marca = texto(slide, "marca", 28, 40, 150, 40, "Prumo.", 30, BRANCO, negrito=True)
    marca.TextFrame.TextRange.Characters(6, 1).Font.Color.RGB = rgb(AMBAR)
    texto(slide, "marca_sub", 30, 82, 150, 20, "materiais de construção", 11, TEXTO_2)
    for (outra, dados), y in zip(PAGINAS.items(), MENU_Y):
        ativa = outra == chave
        if ativa:
            forma(slide, f"menu_{outra}_marcador", 0, y - 4, 4, 30, AMBAR)
        texto(slide, f"menu_{outra}", 32, y, 150, 24, dados["menu"], 14, AMBAR if ativa else MENU,
              fonte="Segoe UI Semibold" if ativa else "Segoe UI")
    texto(slide, "rodape", 28, 660, 150, 40, "Empresa e dados fictícios,\ngerados em Python", 10, RODAPE)

    # cabeçalho
    texto(slide, "titulo", 214, 28, 700, 34, pagina["titulo"], 26, BRANCO, negrito=True)
    texto(slide, "subtitulo", 214, 64, 700, 20, pagina["subtitulo"], 13, TEXTO_2)

    # cartões, destaque e quadros dos visuais
    for i, x in enumerate(CARTOES_X, start=1):
        vidro(slide, f"card_{i}", x, 96, 248, 80, raio=14)
    d = forma(slide, "destaque", *DESTAQUE, DESTAQUE_1, raio=16, borda=(BRANCO, 0.88))
    degrade(d, DESTAQUE_1, DESTAQUE_2, estilo=1)   # 1 = de cima para baixo
    for nome, (x, y, w, h), titulo in (("segundo", SEGUNDO, pagina["segundo"]),
                                       ("principal", PRINCIPAL, pagina["principal"])):
        vidro(slide, nome, x, y, w, h)
        texto(slide, f"{nome}_titulo", x + 18, y + 14, w - 36, 22, titulo, 14, BRANCO, fonte="Segoe UI Semibold")


def main():
    app = win32com.client.gencache.EnsureDispatch("PowerPoint.Application")
    pres = app.Presentations.Add(False)   # sem janela
    pres.PageSetup.SlideWidth, pres.PageSetup.SlideHeight = 1280 * PX, 720 * PX
    for n, (chave, pagina) in enumerate(PAGINAS.items(), start=1):
        slide = pres.Slides.Add(n, 12)   # 12 = slide em branco
        desenhar(slide, chave, pagina)
        slide.Export(str(PASTA / f"fundo_{chave}.png"), "PNG", 1920, 1080)
        print(f"fundo_{chave}.png")
    pres.SaveAs(str(PASTA / "layout_paginas.pptx"))
    pres.Close()
    if app.Presentations.Count == 0:   # não fecha o PowerPoint se o Pedro estiver usando
        app.Quit()


if __name__ == "__main__":
    main()
