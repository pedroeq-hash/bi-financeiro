"""Confere a coerência dos CSVs e se a história continua de pé.

Uso (depois de gerar os dados):  python gerador/test_gerar_dados.py   ou   pytest gerador
"""
import numpy as np
import pandas as pd

import gerar_dados as g

D = g.ler_dados()
TR, TP, LANC = D["titulos_receber"], D["titulos_pagar"], D["lancamentos"]
DRE = g.dre_anual(LANC, D["plano_contas"])
SALDO = g.saldo_mensal(TR, TP, D["saldo_inicial"].saldo.iloc[0])
DEZ = {ano: pd.Timestamp(f"{ano}-12-31") for ano in (2023, 2024, 2025)}


def por_mes(df, coluna_data, coluna_valor="valor"):
    df = df[df[coluna_data] >= g.INICIO]
    return df.groupby(df[coluna_data].dt.to_period("M"))[coluna_valor].sum()


def iguais(a, b):
    a, b = a.align(b, fill_value=0)
    return np.allclose(a, b, atol=1.0)   # tolerância de R$ 1 por mês (arredondamento de centavos)


# ---------------------------------------------------------------- coerência
def test_receita_da_dre_igual_as_vendas():
    assert iguais(por_mes(LANC[LANC.conta_id == 1], "data_competencia"), por_mes(TR, "data_emissao"))


def test_cmv_igual_as_compras():
    cmv = -por_mes(LANC[LANC.conta_id == 3], "data_competencia")
    assert iguais(cmv, por_mes(TP[TP.conta_id == 3], "data_emissao"))


def test_toda_despesa_com_caixa_tem_titulo():
    for conta in set(TP.conta_id) - {3, 15}:
        lanc = -por_mes(LANC[LANC.conta_id == conta], "data_competencia")
        assert iguais(lanc, por_mes(TP[TP.conta_id == conta], "data_emissao")), f"conta {conta}"


def test_perdas_da_dre_iguais_as_baixas_sem_recebimento():
    perdas = TR[TR.valor_recebido == 0]
    assert iguais(-por_mes(LANC[LANC.conta_id == 6], "data_competencia"), por_mes(perdas, "data_recebimento"))


def test_baixas_validas():
    aberto = TR.data_recebimento.isna()
    assert (aberto == TR.valor_recebido.isna()).all()
    pago = TR[~aberto]
    assert ((pago.valor_recebido == pago.valor) | (pago.valor_recebido == 0)).all()
    assert (pago.data_recebimento >= pago.data_emissao).all()
    assert TR.data_recebimento.max() <= g.DATA_CORTE and TP.data_pagamento.max() <= g.DATA_CORTE


def test_orcamento_completo():
    assert len(D["orcamento"]) == 36 * 13   # 36 meses x 14 contas da DRE, menos juros (ninguém orçou ficar no vermelho)


# ---------------------------------------------------------------- história
def test_vendas_crescem():
    cresc = DRE["Receita bruta"].pct_change().dropna()
    assert cresc.between(0.12, 0.22).all(), cresc


def test_pmr_sobe_e_pmp_fica():
    assert 30 <= g.pmr(TR, DEZ[2023]) <= 40
    assert 55 <= g.pmr(TR, DEZ[2025]) <= 70
    assert all(25 <= g.pmp(TP, ref) <= 35 for ref in DEZ.values())


def test_inadimplencia_sobe():
    assert g.inadimplencia_90(TR, DEZ[2023]) < 0.03
    assert g.inadimplencia_90(TR, DEZ[2025]) > 0.045


def test_frete_estoura_em_2025():
    orc = D["orcamento"]
    frete_orc = -orc[(orc.conta_id == 10) & (orc.mes.dt.year == 2025)].valor_orcado.sum()
    assert DRE.loc[2025, "Frete"] > 1.2 * frete_orc
    assert DRE["Frete"].pct_change()[2025] > DRE["Receita bruta"].pct_change()[2025]


def test_lucro_positivo_mas_margem_cai():
    margem = DRE["Lucro líquido"] / DRE["Receita líquida"]
    assert (DRE["Lucro líquido"] > 0).all()
    assert margem[2023] > 0.07 and margem[2025] < 0.065 and margem[2023] - margem[2025] > 0.02


def test_caixa_fica_negativo_so_em_2025():
    assert (SALDO[SALDO.index.year < 2025] > 0).all()
    assert (SALDO[SALDO.index.year == 2025] < 0).sum() >= 2
    juros = por_mes(LANC[LANC.conta_id == 12], "data_competencia")
    assert juros.index.year.min() == 2025   # juros de capital de giro só aparecem quando o caixa fura


if __name__ == "__main__":
    testes = [f for nome, f in sorted(globals().items()) if nome.startswith("test_")]
    for teste in testes:
        teste()
        print("ok ", teste.__name__)
    print(f"\n{len(testes)} testes passaram")
