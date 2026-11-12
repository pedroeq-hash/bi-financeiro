"""Gera os dados fictícios da Prumo Materiais, distribuidora de materiais de construção.

Uso:  python gerador/gerar_dados.py   (grava os CSVs em data/ e imprime um resumo anual)

A empresa e os números são inventados. A "história" que o dashboard conta está nos
parâmetros abaixo: mexa neles e rode gerador/test_gerar_dados.py para ver se ela se mantém.
"""
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

PASTA_DADOS = Path(__file__).resolve().parent.parent / "data"

# ---------------------------------------------------------------- parâmetros da história
SEMENTE = 42
INICIO = pd.Timestamp("2023-01-01")            # início do período analisado (DRE e orçamento)
INICIO_SIMULACAO = pd.Timestamp("2022-10-01")  # 3 meses antes: jan/2023 já começa com títulos em aberto
DATA_CORTE = pd.Timestamp("2025-12-31")        # "hoje" dos dados: baixas depois disso ficam em aberto

# Vendas
RECEITA_ANUAL_BASE = 16_000_000   # ritmo anual de receita bruta em jan/2023 (antes da sazonalidade)
CRESCIMENTO = 0.17                # crescimento real das vendas ao ano
CRESCIMENTO_ORCADO = 0.15         # crescimento que o orçamento previa
SAZONALIDADE = [0.75, 0.80, 0.95, 1.00, 1.00, 0.95, 1.00, 1.05, 1.15, 1.20, 1.15, 1.00]  # jan..dez
DIAS_UTEIS_ANO = 261

# A virada: o comercial passa a dar prazo longo e entra o segmento "Construtora pequena".
DATA_VIRADA = pd.Timestamp("2024-07-01")
RAMPA_MESES = 12   # a mudança se espalha ao longo de 12 meses (completa em jul/2025)

SEGMENTOS = ["Loja", "Construtora", "Construtora pequena", "Consumidor"]
MIX_ANTES = {"Loja": 0.45, "Construtora": 0.35, "Construtora pequena": 0.00, "Consumidor": 0.20}   # % da receita
MIX_DEPOIS = {"Loja": 0.38, "Construtora": 0.30, "Construtora pequena": 0.20, "Consumidor": 0.12}
TICKET_MEDIO = {"Loja": 2_500, "Construtora": 6_000, "Construtora pequena": 2_500, "Consumidor": 600}
# Prazo de cada parcela, em dias da emissão. Consumidor paga no cartão (a empresa recebe em 30 dias).
PRAZOS_ANTES = {"Loja": [28], "Construtora": [30], "Construtora pequena": [30], "Consumidor": [30]}
PRAZOS_DEPOIS = {"Loja": [30, 60], "Construtora": [30, 60, 90], "Construtora pequena": [30, 60, 90], "Consumidor": [30]}
PROB_CALOTE = {"Loja": 0.007, "Construtora": 0.007, "Construtora pequena": 0.25, "Consumidor": 0.0}  # por parcela
ATRASO_MEDIO = {"Loja": 3, "Construtora": 5, "Construtora pequena": 25, "Consumidor": 0}  # dias após o vencimento
DIAS_ATE_PERDA = 180   # parcela não paga 180 dias após o vencimento é baixada como perda

# DRE, em % da receita bruta
IMPOSTOS = 0.16
CMV = 0.56
VARIACAO_CMV = 0.03   # desvio-padrão diário do custo das compras (margem bruta não fica cravada)
COMISSAO = 0.025
FRETE = {2022: 0.045, 2023: 0.045, 2024: 0.055, 2025: 0.072}   # a logística sai do controle em 2025
FRETE_ORCADO = 0.045
PERDAS_ORCADO = 0.008
IR_CSLL = 0.34   # sobre o lucro antes do IR, quando positivo
# Despesas fixas mensais em 2023 (reajustadas todo janeiro)
FIXAS = {"Marketing": 15_000, "Salários e encargos": 70_000, "Aluguel": 25_000,
         "Sistemas e serviços": 12_000, "Tarifas bancárias": 3_000}
REAJUSTE = 0.05
DEPRECIACAO = 15_000   # mensal, não sai do caixa

# Caixa
PMP = 30                     # prazo dos fornecedores de mercadoria, em dias
TAXA_JUROS_MES = 0.025       # juros da conta garantida (capital de giro) sobre o saldo negativo
DISTRIBUICAO_LUCROS = 0.80   # parte do lucro líquido do mês que os sócios retiram no mês seguinte
SALDO_INICIAL = 800_000      # caixa em 01/01/2023

# ---------------------------------------------------------------- cadastros
# conta_id, conta, grupo_dre
CONTAS = [
    (1, "Venda de mercadorias", "Receita bruta"),
    (2, "Impostos sobre vendas", "Deduções"),
    (3, "Custo das mercadorias vendidas", "CMV"),
    (4, "Comissões de vendas", "Despesas comerciais"),
    (5, "Marketing", "Despesas comerciais"),
    (6, "Perdas com clientes", "Despesas comerciais"),
    (7, "Salários e encargos", "Despesas administrativas"),
    (8, "Aluguel", "Despesas administrativas"),
    (9, "Sistemas e serviços", "Despesas administrativas"),
    (10, "Fretes e entregas", "Logística"),
    (11, "Depreciação", "Depreciação"),
    (12, "Juros de capital de giro", "Resultado financeiro"),
    (13, "Tarifas bancárias", "Resultado financeiro"),
    (14, "IR e CSLL", "IR/CSLL"),
    (15, "Distribuição de lucros", "Fora da DRE"),   # sai do caixa, mas não é despesa
]
# Posição do grupo na DRE; os buracos (3, 5, 9, 12, 14) são os subtotais.
ORDEM_DRE = {"Receita bruta": 1, "Deduções": 2, "CMV": 4, "Despesas comerciais": 6,
             "Despesas administrativas": 7, "Logística": 8, "Depreciação": 10,
             "Resultado financeiro": 11, "IR/CSLL": 13, "Fora da DRE": 99}
ID_CONTA = {nome: i for i, nome, _ in CONTAS}
SEM_CAIXA = {1, 3, 6, 11}   # receita e CMV têm títulos próprios; perdas e depreciação não movem caixa
# Dia do mês seguinte em que cada despesa mensal vence (None = debitada no último dia do próprio mês)
DIA_VENCIMENTO = {2: 20, 4: 10, 5: 15, 7: 5, 8: 10, 9: 15, 10: 20, 12: None, 13: None, 14: 28, 15: 15}

SOBRENOMES = ["Silva", "Souza", "Oliveira", "Pereira", "Costa", "Rodrigues", "Almeida", "Nascimento",
              "Lima", "Araújo", "Fernandes", "Carvalho", "Gomes", "Martins", "Rocha", "Ribeiro",
              "Alves", "Monteiro", "Mendes", "Barros", "Freitas", "Barbosa", "Pinto", "Moura",
              "Cavalcanti", "Dias", "Castro", "Campos", "Cardoso", "Teixeira"]
PRENOMES = ["Ana", "Bruno", "Carla", "Daniel", "Eduarda", "Felipe", "Gabriela", "Henrique", "Isabela",
            "João", "Karina", "Lucas", "Mariana", "Nelson", "Patrícia", "Rafael", "Sandra", "Tiago",
            "Vanessa", "Wagner"]
NOMES_SEGMENTO = {  # (modelos de nome, quantidade de clientes)
    "Loja": (["Casa {s} Materiais", "Depósito {s}", "{s} & Filhos Materiais", "Empório {s} da Construção",
              "Materiais {s}"], 150),
    "Construtora": (["Construtora {s}", "{s} Engenharia", "{s} Empreendimentos"], 60),
    "Construtora pequena": (["{s} Reformas", "{s} Obras", "Mestre {s} Construções", "{s} Acabamentos"], 100),
    "Consumidor": (None, 300),
}
CIDADES = [("SP", "Campinas", 5), ("SP", "Sorocaba", 3), ("SP", "Jundiaí", 3), ("SP", "Ribeirão Preto", 2),
           ("SP", "São José dos Campos", 2), ("MG", "Pouso Alegre", 2), ("MG", "Uberlândia", 1),
           ("MG", "Poços de Caldas", 1), ("PR", "Londrina", 1), ("PR", "Maringá", 1)]
# fornecedor, categoria, conta que ele atende (None = mercadoria/frete, sorteados)
FORNECEDORES = [
    ("Cimenteira Horizonte", "Mercadorias"), ("Aços Ipê", "Mercadorias"), ("Tintas Aurora", "Mercadorias"),
    ("Cerâmica Monte Verde", "Mercadorias"), ("Tubos e Conexões Rio Claro", "Mercadorias"),
    ("Madeireira Jatobá", "Mercadorias"), ("Elétrica Faísca", "Mercadorias"), ("Telhas Planalto", "Mercadorias"),
    ("Transportes Rota Sul", "Transportadoras"), ("Logística Via Norte", "Transportadoras"),
    ("Fisco (tributos)", "Tributos"), ("Folha de pagamento", "Pessoal"), ("Imóveis Paineiras", "Serviços"),
    ("Agência Ponto Criativo", "Serviços"), ("Sistemas Ábaco Software", "Serviços"),
    ("Banco (conta garantida)", "Banco"), ("Sócios", "Sócios"),
]
FORNECEDOR_DA_CONTA = {2: "Fisco (tributos)", 4: "Folha de pagamento", 5: "Agência Ponto Criativo",
                       7: "Folha de pagamento", 8: "Imóveis Paineiras", 9: "Sistemas Ábaco Software",
                       12: "Banco (conta garantida)", 13: "Banco (conta garantida)", 14: "Fisco (tributos)",
                       15: "Sócios"}


# ---------------------------------------------------------------- geração
def progresso_virada(data):
    """0 antes da virada, sobe até 1 ao longo de RAMPA_MESES."""
    return float(np.clip((data - DATA_VIRADA).days / 30.44 / RAMPA_MESES, 0, 1))


def receita_esperada_dia(data, crescimento):
    anos = (data - INICIO).days / 365.25
    return (RECEITA_ANUAL_BASE / DIAS_UTEIS_ANO * (1 + crescimento) ** anos
            * SAZONALIDADE[data.month - 1] / np.mean(SAZONALIDADE))


def gerar_clientes(rng):
    pesos = np.array([p for *_, p in CIDADES], dtype=float)
    linhas = []
    for seg in SEGMENTOS:
        modelos, qtd = NOMES_SEGMENTO[seg]
        if modelos:
            nomes = [m.format(s=s) for m in modelos for s in SOBRENOMES]
        else:
            nomes = [f"{p} {s}" for p in PRENOMES for s in SOBRENOMES]
        for nome in rng.choice(nomes, size=qtd, replace=False):
            uf, cidade, _ = CIDADES[rng.choice(len(CIDADES), p=pesos / pesos.sum())]
            linhas.append({"cliente_id": f"C{len(linhas) + 1:04d}", "nome": nome, "segmento": seg,
                           "uf": uf, "cidade": cidade})
    return pd.DataFrame(linhas)


def gerar_fornecedores():
    return pd.DataFrame([{"fornecedor_id": f"F{i:03d}", "nome": n, "categoria": c}
                         for i, (n, c) in enumerate(FORNECEDORES, start=1)])


def gerar_titulos_receber(rng, clientes):
    """Uma linha por parcela. Cada nota de venda vira 1 a 3 parcelas."""
    ids_por_seg = {s: clientes.loc[clientes.segmento == s, "cliente_id"].to_numpy() for s in SEGMENTOS}
    sigma = 0.5   # dispersão do valor das notas
    linhas, nota = [], 0
    for dia in pd.bdate_range(INICIO_SIMULACAO, DATA_CORTE):
        receita_dia = receita_esperada_dia(dia, CRESCIMENTO)
        p = progresso_virada(dia)
        for seg in SEGMENTOS:
            fatia = MIX_ANTES[seg] + p * (MIX_DEPOIS[seg] - MIX_ANTES[seg])
            for _ in range(rng.poisson(receita_dia * fatia / TICKET_MEDIO[seg])):
                nota += 1
                valor = round(rng.lognormal(np.log(TICKET_MEDIO[seg]) - sigma ** 2 / 2, sigma), 2)
                prazos = (PRAZOS_DEPOIS if rng.random() < p else PRAZOS_ANTES)[seg]
                parcela = round(valor / len(prazos), 2)
                valores = [parcela] * (len(prazos) - 1) + [round(valor - parcela * (len(prazos) - 1), 2)]
                cliente = rng.choice(ids_por_seg[seg])
                for n, (prazo, v) in enumerate(zip(prazos, valores), start=1):
                    venc = dia + pd.Timedelta(days=prazo)
                    if rng.random() < PROB_CALOTE[seg]:
                        baixa, recebido = venc + pd.Timedelta(days=DIAS_ATE_PERDA), 0.0   # vira perda
                    else:
                        atraso = min(int(rng.exponential(ATRASO_MEDIO[seg])), DIAS_ATE_PERDA - 10) if ATRASO_MEDIO[seg] else 0
                        baixa, recebido = venc + pd.Timedelta(days=atraso), v
                    linhas.append({"titulo_id": f"NF{nota:06d}-{n}", "cliente_id": cliente, "data_emissao": dia,
                                   "data_vencimento": venc, "data_recebimento": baixa,
                                   "valor": v, "valor_recebido": recebido})
    tr = pd.DataFrame(linhas)
    depois_do_corte = tr.data_recebimento > DATA_CORTE
    tr.loc[depois_do_corte, "data_recebimento"] = pd.NaT   # ainda em aberto "hoje"
    tr.loc[depois_do_corte, "valor_recebido"] = np.nan
    return tr


def gerar_dados(rng):
    clientes = gerar_clientes(rng)
    fornecedores = gerar_fornecedores()
    id_forn = dict(zip(fornecedores.nome, fornecedores.fornecedor_id))
    forn_mercadoria = fornecedores.loc[fornecedores.categoria == "Mercadorias", "fornecedor_id"].to_numpy()
    forn_frete = fornecedores.loc[fornecedores.categoria == "Transportadoras", "fornecedor_id"].to_numpy()

    tr = gerar_titulos_receber(rng, clientes)
    vendas_dia = tr.groupby("data_emissao").valor.sum()
    mes = lambda s: s.dt.to_period("M")
    receita_mes = vendas_dia.groupby(vendas_dia.index.to_period("M")).sum()
    recebido_mes = tr[tr.data_recebimento >= INICIO].groupby(mes(tr.data_recebimento)).valor_recebido.sum()
    perdas = tr[tr.valor_recebido == 0]
    perdas_mes = perdas.groupby(mes(perdas.data_recebimento)).valor.sum()

    pagar, pago_mes = [], defaultdict(float)

    def novo_titulo(fornecedor, conta, emissao, vencimento, valor):
        pagamento = vencimento if vencimento <= DATA_CORTE else pd.NaT   # a Prumo paga em dia
        pagar.append({"titulo_id": f"P{len(pagar) + 1:06d}", "fornecedor_id": fornecedor, "conta_id": conta,
                      "data_emissao": emissao, "data_vencimento": vencimento,
                      "data_pagamento": pagamento, "valor": round(valor, 2)})
        if pd.notna(pagamento):
            pago_mes[pagamento.to_period("M")] += round(valor, 2)

    # Compras de mercadoria acompanham as vendas do dia (sem estoque) e vencem em PMP dias.
    for dia, venda in vendas_dia.items():
        novo_titulo(rng.choice(forn_mercadoria), ID_CONTA["Custo das mercadorias vendidas"],
                    dia, dia + pd.Timedelta(days=PMP), CMV * venda * rng.normal(1, VARIACAO_CMV))
    compras = pd.DataFrame(pagar)
    cmv_mes = compras.groupby(mes(compras.data_emissao)).valor.sum()

    # Laço mensal: juros dependem do saldo do mês anterior e a distribuição, do lucro do mês.
    lancamentos, saldo = [], SALDO_INICIAL
    for periodo in pd.period_range(INICIO_SIMULACAO, DATA_CORTE, freq="M"):
        fim = periodo.end_time.normalize()
        receita = receita_mes.get(periodo, 0.0)
        valores = despesas_do_mes(receita, periodo.year, FRETE[periodo.year])
        valores[ID_CONTA["Custo das mercadorias vendidas"]] = cmv_mes.get(periodo, 0.0)
        valores[ID_CONTA["Perdas com clientes"]] = perdas_mes.get(periodo, 0.0)
        valores[ID_CONTA["Juros de capital de giro"]] = TAXA_JUROS_MES * max(0.0, -saldo) if fim >= INICIO else 0.0
        lair = receita - sum(valores.values())
        valores[ID_CONTA["IR e CSLL"]] = IR_CSLL * max(0.0, lair)
        lucro = receita - sum(valores.values())
        valores = {c: round(v, 2) for c, v in valores.items()}

        frete = valores[ID_CONTA["Fretes e entregas"]]
        for conta, valor in list(valores.items()) + [(15, DISTRIBUICAO_LUCROS * max(0.0, lucro))]:
            if conta in SEM_CAIXA or valor <= 0:
                continue
            dia = DIA_VENCIMENTO[conta]
            venc = fim if dia is None else (periodo + 1).start_time + pd.Timedelta(days=dia - 1)
            if conta == ID_CONTA["Fretes e entregas"]:   # frete dividido entre as transportadoras
                for f, parte in zip(forn_frete, (0.6, 0.4)):
                    novo_titulo(f, conta, fim, venc, frete * parte)
            else:
                novo_titulo(id_forn[FORNECEDOR_DA_CONTA[conta]], conta, fim, venc, valor)
        if fim >= INICIO:
            lancamentos += [{"data_competencia": fim, "conta_id": c, "valor": -v} for c, v in valores.items() if v]
            saldo += recebido_mes.get(periodo, 0.0) - pago_mes.get(periodo, 0.0)

    # Receita: um lançamento por nota de venda, na data de emissão.
    notas = tr.assign(nota=tr.titulo_id.str.split("-").str[0]).groupby(["nota", "data_emissao"]).valor.sum().reset_index()
    notas = notas[notas.data_emissao >= INICIO]
    receita_lanc = pd.DataFrame({"data_competencia": notas.data_emissao, "conta_id": 1, "valor": notas.valor.round(2)})
    lancamentos = pd.concat([receita_lanc, pd.DataFrame(lancamentos)], ignore_index=True)

    return {
        "plano_contas": pd.DataFrame([{"conta_id": i, "conta": n, "grupo_dre": g, "ordem_dre": ORDEM_DRE[g]}
                                      for i, n, g in CONTAS]),
        "lancamentos": lancamentos.sort_values(["data_competencia", "conta_id"]),
        "orcamento": gerar_orcamento(),
        "titulos_receber": tr,
        "titulos_pagar": pd.DataFrame(pagar),
        "clientes": clientes,
        "fornecedores": fornecedores,
        "saldo_inicial": pd.DataFrame([{"data": INICIO, "saldo": SALDO_INICIAL}]),
    }


def despesas_do_mes(receita, ano, frete_pct):
    """Valores positivos das despesas que dependem só da receita e do ano."""
    fator = (1 + REAJUSTE) ** (ano - INICIO.year)
    valores = {ID_CONTA[nome]: valor * fator for nome, valor in FIXAS.items()}
    valores[ID_CONTA["Impostos sobre vendas"]] = IMPOSTOS * receita
    valores[ID_CONTA["Comissões de vendas"]] = COMISSAO * receita
    valores[ID_CONTA["Fretes e entregas"]] = frete_pct * receita
    valores[ID_CONTA["Depreciação"]] = DEPRECIACAO
    return valores


def gerar_orcamento():
    """Orçamento mensal por conta, com as premissas do plano: crescimento-meta e frete sob controle."""
    linhas = []
    for periodo in pd.period_range(INICIO, DATA_CORTE, freq="M"):
        dias = pd.bdate_range(periodo.start_time, periodo.end_time)
        receita = sum(receita_esperada_dia(d, CRESCIMENTO_ORCADO) for d in dias)
        valores = despesas_do_mes(receita, periodo.year, FRETE_ORCADO)
        valores[ID_CONTA["Custo das mercadorias vendidas"]] = CMV * receita
        valores[ID_CONTA["Perdas com clientes"]] = PERDAS_ORCADO * receita
        valores[ID_CONTA["IR e CSLL"]] = IR_CSLL * max(0.0, receita - sum(valores.values()))
        linhas.append({"mes": periodo.start_time, "conta_id": 1, "valor_orcado": round(receita, 2)})
        linhas += [{"mes": periodo.start_time, "conta_id": c, "valor_orcado": -round(v, 2)} for c, v in valores.items()]
    return pd.DataFrame(linhas).sort_values(["mes", "conta_id"])


# ---------------------------------------------------------------- indicadores (os mesmos das medidas DAX)
JANELA = pd.Timedelta(days=90)


def em_aberto(titulos, ref, coluna_baixa):
    """Títulos emitidos até ref e ainda não baixados em ref."""
    t = titulos
    return t[(t.data_emissao <= ref) & (t[coluna_baixa].isna() | (t[coluna_baixa] > ref))]


def emitidos_90d(titulos, ref):
    return titulos[(titulos.data_emissao > ref - JANELA) & (titulos.data_emissao <= ref)].valor.sum()


def pmr(tr, ref):
    """Prazo médio de recebimento: saldo a receber ÷ vendas dos últimos 90 dias × 90."""
    return em_aberto(tr, ref, "data_recebimento").valor.sum() / emitidos_90d(tr, ref) * 90


def pmp(tp, ref):
    """Prazo médio de pagamento a fornecedores de mercadoria (mesma lógica do PMR)."""
    compras = tp[tp.conta_id == ID_CONTA["Custo das mercadorias vendidas"]]
    return em_aberto(compras, ref, "data_pagamento").valor.sum() / emitidos_90d(compras, ref) * 90


def inadimplencia_90(tr, ref):
    """Saldo vencido há mais de 90 dias ÷ saldo a receber."""
    aberto = em_aberto(tr, ref, "data_recebimento")
    return aberto[aberto.data_vencimento < ref - JANELA].valor.sum() / aberto.valor.sum()


def saldo_mensal(tr, tp, saldo_inicial):
    """Saldo de caixa no fim de cada mês, a partir das baixas dos títulos."""
    entradas = tr[tr.data_recebimento >= INICIO].groupby(tr.data_recebimento.dt.to_period("M")).valor_recebido.sum()
    saidas = tp[tp.data_pagamento >= INICIO].groupby(tp.data_pagamento.dt.to_period("M")).valor.sum()
    meses = pd.period_range(INICIO, DATA_CORTE, freq="M")
    return saldo_inicial + (entradas.reindex(meses, fill_value=0) - saidas.reindex(meses, fill_value=0)).cumsum()


def dre_anual(lancamentos, plano):
    """Subtotais da DRE por ano: soma dos grupos com ordem menor que a do subtotal."""
    l = lancamentos.merge(plano, on="conta_id")
    l = l[l.grupo_dre != "Fora da DRE"]
    ano = l.data_competencia.dt.year
    sub = lambda ordem: l[l.ordem_dre < ordem].groupby(ano).valor.sum()
    return pd.DataFrame({"Receita bruta": sub(2), "Receita líquida": sub(3), "Lucro bruto": sub(5),
                         "EBITDA": sub(9), "Lucro líquido": sub(14),
                         "Frete": -l[l.conta_id == ID_CONTA["Fretes e entregas"]].groupby(ano).valor.sum()})


def ler_dados(pasta=PASTA_DADOS):
    datas = ["data_emissao", "data_vencimento", "data_recebimento", "data_pagamento", "data_competencia", "mes", "data"]
    dados = {}
    for arq in sorted(pasta.glob("*.csv")):
        df = pd.read_csv(arq, encoding="utf-8")
        for c in df.columns.intersection(datas):
            df[c] = pd.to_datetime(df[c])
        dados[arq.stem] = df
    return dados


def resumo(d):
    tr, tp = d["titulos_receber"], d["titulos_pagar"]
    dre = dre_anual(d["lancamentos"], d["plano_contas"])
    saldo = saldo_mensal(tr, tp, d["saldo_inicial"].saldo.iloc[0])
    orc = d["orcamento"]
    frete_orc = -orc[orc.conta_id == ID_CONTA["Fretes e entregas"]].groupby(orc.mes.dt.year).valor_orcado.sum()
    linhas = {}
    for ano in dre.index:
        ref = pd.Timestamp(f"{ano}-12-31")
        r = dre.loc[ano]
        s = saldo[saldo.index.year == ano]
        linhas[ano] = {
            "Receita bruta (R$ mi)": r["Receita bruta"] / 1e6,
            "% Margem bruta": r["Lucro bruto"] / r["Receita líquida"] * 100,
            "% Margem EBITDA": r["EBITDA"] / r["Receita líquida"] * 100,
            "Lucro líquido (R$ mi)": r["Lucro líquido"] / 1e6,
            "% Margem líquida": r["Lucro líquido"] / r["Receita líquida"] * 100,
            "Frete realizado/orçado": r["Frete"] / frete_orc[ano],
            "PMR em 31/12 (dias)": pmr(tr, ref),
            "PMP em 31/12 (dias)": pmp(tp, ref),
            "% Inadimplência 90+": inadimplencia_90(tr, ref) * 100,
            "Menor saldo mensal (R$ mil)": s.min() / 1e3,
            "Meses com caixa negativo": int((s < 0).sum()),
        }
    return pd.DataFrame(linhas)


def main():
    rng = np.random.default_rng(SEMENTE)
    dados = gerar_dados(rng)
    PASTA_DADOS.mkdir(exist_ok=True)
    for nome, df in dados.items():
        df.to_csv(PASTA_DADOS / f"{nome}.csv", index=False, encoding="utf-8", float_format="%.2f")
        print(f"{nome}.csv: {len(df):,} linhas")
    d = ler_dados()
    print("\nResumo anual\n" + resumo(d).round(1).to_string())
    print("\nSaldo de caixa no fim do mês (R$ mil)\n"
          + (saldo_mensal(d["titulos_receber"], d["titulos_pagar"], SALDO_INICIAL) / 1e3).round(0).to_string())


if __name__ == "__main__":
    main()
