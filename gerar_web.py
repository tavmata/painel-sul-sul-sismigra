"""
Gera docs/dados.json, a base da versão web do painel (docs/index.html, publicada no GitHub Pages).

Lê as tabelas de tabelas/ (saída de preparar_dados.py) e grava "cubos" pequenos: contagens por
ano × país × atributo. Os filtros da página web (anos, critério de Sul Global, região, país) agem sobre
ano e país, então cada gráfico é uma soma sobre um desses cubos.

Uso:  python gerar_web.py
"""
import json
import os
import sys
from datetime import date

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
AQUI = os.path.dirname(os.path.abspath(__file__))
TAB = os.path.join(AQUI, "tabelas")
SAIDA = os.path.join(AQUI, "docs", "dados.json")

if not os.path.exists(os.path.join(TAB, "fato_registros.csv")):
    raise SystemExit("Rode antes: python preparar_dados.py")


def ler(nome):
    return pd.read_csv(os.path.join(TAB, nome), sep=";", dtype=str, keep_default_na=False)


fato = ler("fato_registros.csv")
fato["Quantidade"] = fato["Quantidade"].astype(int)
fato["Ano"] = fato["Ano"].astype(int)
paises = ler("dim_pais.csv")
prof = ler("dim_profissao.csv")
ufs = ler("dim_uf.csv")
anos_dim = ler("dim_ano.csv")
anos_dim["Ano"] = anos_dim["Ano"].astype(int)
faixas = ler("dim_faixa_etaria.csv")["Faixa etária"].tolist()

# ---------------------------------------------------------------- dicionários
anos = sorted(fato["Ano"].unique().tolist())
rotulo_ano = dict(zip(anos_dim["Ano"], anos_dim["Ano (rótulo)"]))
paises["_or"] = paises["Ordem região"].astype(int)
paises["_os"] = paises["Ordem sub-região"].astype(int)
paises = paises.sort_values(["_or", "_os", "País"])  # ordem M49: região › sub-região › país
paises = paises[paises["País"].isin(set(fato["País"]))]
pais_idx = {p: i for i, p in enumerate(paises["País"])}
GRUPO = {"Sul Global": 1, "Norte Global": 0, "Indeterminado": -1}


def lista_por_total(col, ordem=None):
    """Valores da coluna em ordem fixa (se dada) ou do maior para o menor total."""
    if ordem:
        return [v for v in ordem if v in set(fato[col])]
    return fato.groupby(col)["Quantidade"].sum().sort_values(ascending=False).index.tolist()


dims = {
    "sexo": lista_por_total("Sexo", ["Feminino", "Masculino", "Não informado"]),
    "faixa": lista_por_total("Faixa etária", faixas),
    "civil": lista_por_total("Estado civil"),
    "tip": lista_por_total("Tipologia de amparo"),
    "cls": lista_por_total("Classificação do registro"),
    "prof": lista_por_total("Profissão"),
    "uf": lista_por_total("UF"),
    "mun": lista_por_total("Município (UF)"),
}
grupo_da_prof = dict(zip(prof["Profissão"], prof["Grupo ocupacional"]))
ordem_grupo = dict(zip(prof["Grupo ocupacional"], prof["Ordem grupo"].astype(int)))
dims["grupo"] = sorted(set(grupo_da_prof.values()), key=lambda g: ordem_grupo[g])
fato["Grupo ocupacional"] = fato["Profissão"].map(grupo_da_prof)
uf_nome = dict(zip(ufs["UF"], ufs["Unidade da Federação"]))
uf_regiao = dict(zip(ufs["UF"], ufs["Região do Brasil"]))
idx = {k: {v: i for i, v in enumerate(vs)} for k, vs in dims.items()}


def cubo(*colunas_dim):
    """Lista plana [ano_i, pais_i, d1_i, ..., n, ...] somando Quantidade."""
    cols = ["Ano", "País"] + [c for c, _ in colunas_dim]
    g = fato.groupby(cols, observed=True)["Quantidade"].sum().reset_index()
    out = []
    a_idx = {a: i for i, a in enumerate(anos)}
    for row in g.itertuples(index=False):
        vals = [a_idx[row[0]], pais_idx[row[1]]]
        for (c, d), v in zip(colunas_dim, row[2:-1]):
            vals.append(idx[d][v])
        vals.append(int(row[-1]))
        out.extend(vals)
    return out


cubos = {
    "total": cubo(),
    "sexo": cubo(("Sexo", "sexo")),
    "faixa_sexo": cubo(("Faixa etária", "faixa"), ("Sexo", "sexo")),
    "civil": cubo(("Estado civil", "civil")),
    "grupo": cubo(("Grupo ocupacional", "grupo")),
    "prof": cubo(("Profissão", "prof")),
    "tip": cubo(("Tipologia de amparo", "tip")),
    "cls": cubo(("Classificação do registro", "cls")),
    "uf": cubo(("UF", "uf")),
    "mun": cubo(("Município (UF)", "mun")),
}

dados = {
    "gerado_em": date.today().isoformat(),
    "anos": anos,
    "rotulos_ano": [rotulo_ano[a] for a in anos],
    "paises": [[r["País"], r["Região"], r["Sub-região"], GRUPO[r["Classificação ONU"]], GRUPO[r["Classificação UNCTAD"]]]
               for _, r in paises.iterrows()],
    "dims": dims,
    "grupo_da_prof": [dims["grupo"].index(grupo_da_prof[p]) for p in dims["prof"]],
    "uf_nome": [uf_nome[u] for u in dims["uf"]],
    "uf_regiao": [uf_regiao[u] for u in dims["uf"]],
    "cubos": cubos,
}
# conferência: cada cubo soma o total de registros
total = int(fato["Quantidade"].sum())
for nome, c in cubos.items():
    largura = {"total": 3, "faixa_sexo": 5}.get(nome, 4)
    assert sum(c[largura - 1::largura]) == total, nome

os.makedirs(os.path.dirname(SAIDA), exist_ok=True)
with open(SAIDA, "w", encoding="utf-8") as f:
    json.dump(dados, f, ensure_ascii=False, separators=(",", ":"))
print(f"{SAIDA}: {os.path.getsize(SAIDA) / 1e6:.1f} MB; total {total:,d}")
for nome, c in cubos.items():
    largura = {"total": 3, "faixa_sexo": 5}.get(nome, 4)
    print(f"  {nome:12s} {len(c) // largura:>8,d} células")
