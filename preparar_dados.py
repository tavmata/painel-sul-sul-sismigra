"""
Prepara as tabelas do painel "Migração Sul-Sul no Brasil (SISMIGRA)" para o Power BI.

Entrada : sismigra_*.csv (microdados do SISMIGRA, separador ';', UTF-8), procurados em
          [pasta indicada] > ./dados > pasta-mãe deste script
          referencias/*.csv (classificações editáveis: países, variantes de grafia, profissões)
Saída   : tabelas/*.csv (fato agregado + dimensões), lidas pelo modelo do Power BI

Uso:    python preparar_dados.py [pasta_com_os_csv_do_sismigra]
Rodar de novo sempre que entrar um arquivo novo do SISMIGRA ou mudar uma classificação
em referencias/. Depois, no Power BI: Página Inicial > Atualizar.
"""
import csv
import glob
import os
import re
import sys
import unicodedata
from collections import Counter

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
AQUI = os.path.dirname(os.path.abspath(__file__))


def _pasta_dados():
    candidatas = [sys.argv[1]] if len(sys.argv) > 1 else [os.path.join(AQUI, "dados"), os.path.dirname(AQUI)]
    for c in candidatas:
        if glob.glob(os.path.join(c, "sismigra_*.csv")):
            return os.path.abspath(c)
    raise SystemExit("Nenhum sismigra_*.csv encontrado em: " + ", ".join(candidatas)
                     + "\nBaixe os microdados (ver README) ou informe a pasta: python preparar_dados.py <pasta>")


DADOS = _pasta_dados()
REF = os.path.join(AQUI, "referencias")
SAIDA = os.path.join(AQUI, "tabelas")
os.makedirs(SAIDA, exist_ok=True)

MESES = {"janeiro": "jan", "fevereiro": "fev", "marco": "mar", "abril": "abr", "maio": "mai", "junho": "jun",
         "julho": "jul", "agosto": "ago", "setembro": "set", "outubro": "out", "novembro": "nov"}


def sem_acento(s: str) -> str:
    s = "" if s is None else str(s)
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)).upper().strip()


def ler_ref(nome):
    with open(os.path.join(REF, nome), encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


# ---------------------------------------------------------------- referências
PAISES = ler_ref("paises.csv")
PAIS_ATTR = {p["pais"]: p for p in PAISES}
VARIANTE = {sem_acento(p["pais"]): p["pais"] for p in PAISES}
VARIANTE.update({sem_acento(v["grafia_sismigra"]): v["pais"] for v in ler_ref("paises_variantes.csv")})
for destino in VARIANTE.values():
    assert destino in PAIS_ATTR, f"variante aponta para país inexistente em paises.csv: {destino}"

PROF = {r["grafia_sismigra"]: r for r in ler_ref("profissoes.csv")}
GRUPOS_OCUP = ler_ref("grupos_ocupacionais.csv")

UF_NOME = {
    "AC": ("Acre", "Norte"), "AL": ("Alagoas", "Nordeste"), "AP": ("Amapá", "Norte"), "AM": ("Amazonas", "Norte"),
    "BA": ("Bahia", "Nordeste"), "CE": ("Ceará", "Nordeste"), "DF": ("Distrito Federal", "Centro-Oeste"),
    "ES": ("Espírito Santo", "Sudeste"), "GO": ("Goiás", "Centro-Oeste"), "MA": ("Maranhão", "Nordeste"),
    "MT": ("Mato Grosso", "Centro-Oeste"), "MS": ("Mato Grosso do Sul", "Centro-Oeste"), "MG": ("Minas Gerais", "Sudeste"),
    "PA": ("Pará", "Norte"), "PB": ("Paraíba", "Nordeste"), "PR": ("Paraná", "Sul"), "PE": ("Pernambuco", "Nordeste"),
    "PI": ("Piauí", "Nordeste"), "RJ": ("Rio de Janeiro", "Sudeste"), "RN": ("Rio Grande do Norte", "Nordeste"),
    "RS": ("Rio Grande do Sul", "Sul"), "RO": ("Rondônia", "Norte"), "RR": ("Roraima", "Norte"),
    "SC": ("Santa Catarina", "Sul"), "SP": ("São Paulo", "Sudeste"), "SE": ("Sergipe", "Nordeste"),
    "TO": ("Tocantins", "Norte"),
}

FAIXAS = ["0 a 14 anos", "15 a 24 anos", "25 a 39 anos", "40 a 64 anos", "65 anos ou mais", "Não informado"]
FAIXA_MAP = {
    "0 |-- 15 ANOS": FAIXAS[0], "15 |-- 25 ANOS": FAIXAS[1], "25 |-- 40 ANOS": FAIXAS[2],
    "40 |-- 65 ANOS": FAIXAS[3], "65 |-- ANOS": FAIXAS[4],
}

SEXO_MAP = {"MASCULINO": "Masculino", "FEMININO": "Feminino"}
CIVIL_MAP = {
    "SOLTEIRO": "Solteiro(a)", "CASADO": "Casado(a)", "VIUVO": "Viúvo(a)", "DIVORCIADO": "Divorciado(a)",
    "SEPARADO JUDICIALMENTE": "Separado(a)", "SEPARADO_JUDICIALMENTE": "Separado(a)",
    "SEPARADO CONSENSUALMENTE": "Separado(a)", "DESQUITADO": "Separado(a)", "OUTROS": "Outros", "OUTRO": "Outros",
}
TIPOLOGIA_MAP = {
    "ACOLHIDA VENEZUELANOS": "Acolhida a venezuelanos", "ACORDOS AMERICA DO SUL": "Acordos América do Sul",
    "TRABALHO/INVESTIMENTOS": "Trabalho/investimentos", "REUNIAO FAMILIAR": "Reunião familiar",
    # "Não aplicável" no SISMIGRA = amparo 290 (art. 2º do Decreto 9.277/2018): documento provisório do solicitante de refúgio
    "NAO APLICAVEL": "Solicitação de refúgio (DPRNM)", "ACOLHIDA HUMANITARIA": "Acolhida humanitária", "ESTUDOS": "Estudos",
    "OUTROS": "Outros", "REFUGIO/ASILO": "Refúgio/asilo", "MISSAO RELIGIOSA": "Missão religiosa",
    "FRONTEIRICOS": "Fronteiriços",
}
CLASSIF_MAP = {
    "TEMPORARIO": "Temporário", "RESIDENTE": "Residente", "NAO APLICAVEL": "Solicitante de refúgio (DPRNM)",
    "FRONTEIRICO": "Fronteiriço", "OUTROS": "Outros", "PROVISORIO": "Provisório",
}

PARTICULAS = {"DE", "DA", "DO", "DAS", "DOS", "E", "D"}


def titulo_pt(s: str) -> str:
    palavras = s.lower().split()
    out = []
    for i, p in enumerate(palavras):
        out.append(p if (i > 0 and p.upper() in PARTICULAS) else p[:1].upper() + p[1:])
    return " ".join(out).replace("D'o", "D'O")


def faixa_de_idade(v: str) -> str:
    try:
        i = int(float(v))
    except (TypeError, ValueError):
        return "Não informado"
    if i < 0 or i > 120:
        return "Não informado"
    return FAIXAS[0] if i < 15 else FAIXAS[1] if i < 25 else FAIXAS[2] if i < 40 else FAIXAS[3] if i < 65 else FAIXAS[4]


# ---------------------------------------------------------------- leitura
arquivos = sorted(glob.glob(os.path.join(DADOS, "sismigra_*.csv")))
# Anos parciais: arquivos nomeados "sismigra_janeiro_<mês>_<ano>.csv" com mês diferente de dezembro
PARCIAL = {}
for arq in arquivos:
    m = re.search(r"janeiro_([a-zç]+)_(\d{4})", sem_acento(os.path.basename(arq)).lower())
    if m and m.group(1) in MESES:
        PARCIAL[int(m.group(2))] = MESES[m.group(1)]
print(f"Lendo {len(arquivos)} arquivos do SISMIGRA...")
partes = []
for arq in arquivos:
    df = pd.read_csv(arq, sep=";", encoding="utf-8", dtype=str, keep_default_na=False)
    df.columns = [c.replace("trim(", "").replace(")", "") for c in df.columns]
    if "FAIXA_ETARIA" not in df.columns:
        df["FAIXA_ETARIA"] = df["IDADE"].map(faixa_de_idade)
    df["ARQUIVO"] = os.path.basename(arq)
    print(f"  {os.path.basename(arq):40s} {len(df):>9,d} linhas")
    partes.append(df[["DATAREGISTRO", "PAIS_NACIONALIDADE", "PAIS_NASCIMENTO", "UNIDADE_FED_RESIDENCIA",
                      "MUNICIPIO_RESIDENCIA", "SEXO", "FAIXA_ETARIA", "ESTADO_CIVIL", "PROFISSAO",
                      "TIPOLOGIA_AMPAROS", "CLASSIFICACAO_REVISADA", "ARQUIVO"]])
df = pd.concat(partes, ignore_index=True)
del partes
total_bruto = len(df)
print(f"Total: {total_bruto:,d} registros")

# ---------------------------------------------------------------- harmonização
out = pd.DataFrame({"ano": pd.to_numeric(df["DATAREGISTRO"], errors="coerce").astype("Int64")})
assert out["ano"].notna().all(), "há registros sem ano de registro"

# País: nacionalidade; quando ausente (todo o ano de 2017 no arquivo 2010-2017), país de nascimento.
nac = df["PAIS_NACIONALIDADE"].str.strip()
usa_nasc = nac.eq("")
pais_bruto = nac.where(~usa_nasc, df["PAIS_NASCIMENTO"].str.strip())
chave = pais_bruto.map(sem_acento)
faltando = sorted(set(chave) - set(VARIANTE))
if faltando:
    raise SystemExit("Grafias de país sem classificação (adicione em referencias/paises_variantes.csv):\n  "
                     + "\n  ".join(faltando))
out["pais"] = chave.map(VARIANTE)
out["fonte_pais"] = usa_nasc.map({False: "Nacionalidade", True: "País de nascimento"})

uf = df["UNIDADE_FED_RESIDENCIA"].str.strip().str.upper()
out["uf"] = uf.where(uf.isin(UF_NOME.keys()), uf.map({"EX": "EX"})).fillna("NI")

# Município: remove prefixo "UF_", unifica grafias com/sem acento e põe em caixa de título.
mun = df["MUNICIPIO_RESIDENCIA"].str.strip().str.upper().str.replace(r"^[A-Z]{2}_", "", regex=True)
mun_chave = mun.map(sem_acento)
grafias = Counter(zip(mun_chave, mun))
melhor = {}
for (k, g), n in grafias.most_common():
    atual = melhor.get(k)
    tem_acento = g != sem_acento(g)
    if atual is None or (tem_acento and atual == sem_acento(atual)):
        melhor[k] = g
nao_inf = {"", "-", "NAO ESPECIFICADO", "NAO INFORMADO", "NAO DECLARADO"}
mun_nome = {k: ("Não informado" if k in nao_inf else titulo_pt(v)) for k, v in melhor.items()}
out["municipio"] = mun_chave.map(mun_nome)
out["municipio_uf"] = out["municipio"] + " (" + out["uf"].replace({"NI": "UF não informada", "EX": "Exterior"}) + ")"
out.loc[out["municipio"].eq("Não informado"), "municipio_uf"] = "Não informado"

out["sexo"] = df["SEXO"].map(sem_acento).map(SEXO_MAP).fillna("Não informado")
fx = df["FAIXA_ETARIA"].map(sem_acento)
out["faixa_etaria"] = fx.map(FAIXA_MAP).fillna(df["FAIXA_ETARIA"].where(df["FAIXA_ETARIA"].isin(FAIXAS))).fillna("Não informado")
out["estado_civil"] = df["ESTADO_CIVIL"].map(sem_acento).map(CIVIL_MAP).fillna("Não informado")

prof = df["PROFISSAO"].map(sem_acento)
prof_desconhecida = sorted(set(prof) - set(PROF))
if prof_desconhecida:
    print("AVISO: profissões sem classificação (ficam como 'Não informado'):", prof_desconhecida[:20])
out["profissao"] = prof.map({k: v["profissao"] for k, v in PROF.items()}).fillna("Não informado")

out["tipologia_amparo"] = df["TIPOLOGIA_AMPAROS"].map(sem_acento).map(TIPOLOGIA_MAP).fillna("Não informado")
out["classificacao"] = df["CLASSIFICACAO_REVISADA"].map(sem_acento).map(CLASSIF_MAP).fillna("Não informado")
del df

# ---------------------------------------------------------------- fato agregado
chaves = ["ano", "pais", "fonte_pais", "uf", "municipio_uf", "sexo", "faixa_etaria", "estado_civil",
          "profissao", "tipologia_amparo", "classificacao"]
fato = out.groupby(chaves, observed=True, dropna=False).size().reset_index(name="registros")
assert fato["registros"].sum() == total_bruto
fato.rename(columns={
    "ano": "Ano", "pais": "País", "fonte_pais": "Fonte do país", "uf": "UF", "municipio_uf": "Município (UF)",
    "sexo": "Sexo", "faixa_etaria": "Faixa etária", "estado_civil": "Estado civil", "profissao": "Profissão",
    "tipologia_amparo": "Tipologia de amparo", "classificacao": "Classificação do registro", "registros": "Quantidade",
}).to_csv(os.path.join(SAIDA, "fato_registros.csv"), sep=";", index=False, encoding="utf-8")
print(f"fato_registros.csv: {len(fato):,d} linhas agregadas (soma = {fato['registros'].sum():,d})")

# ---------------------------------------------------------------- dimensões
REGIAO_DE = {
    "África": ["África Setentrional", "África Oriental", "África Central", "África Austral", "África Ocidental"],
    "América Latina e Caribe": ["Caribe", "América Central", "América do Sul"],
    "Ásia": ["Ásia Central", "Ásia Oriental", "Sudeste Asiático", "Ásia Meridional", "Ásia Ocidental"],
    "Oceania": ["Melanésia", "Micronésia", "Polinésia", "Austrália e Nova Zelândia"],
    "América do Norte": ["América do Norte"],
    "Europa": ["Europa Oriental", "Europa Setentrional", "Europa Meridional", "Europa Ocidental"],
    "Indeterminado": ["Indeterminado"],
}
ORDEM_REGIAO = {r: i for i, r in enumerate(REGIAO_DE, 1)}
REGIAO = {s: r for r, subs in REGIAO_DE.items() for s in subs}
ORDEM_SUB = {s: i for i, s in enumerate([s for subs in REGIAO_DE.values() for s in subs], 1)}
NORTE_EXTRA_ONU = {"Japão"}
NORTE_EXTRA_UNCTAD = {"Japão", "Israel", "Coreia do Sul", "Chipre"}
PALOP = {"Angola", "Cabo Verde", "Guiné-Bissau", "Moçambique", "São Tomé e Príncipe"}
CPLP = PALOP | {"Portugal", "Timor-Leste", "Guiné Equatorial"}

usados = set(fato["pais"])
linhas = []
for p in PAISES:
    if p["pais"] not in usados:
        continue
    sub = p["sub_regiao"]
    reg = REGIAO[sub]
    if reg == "Indeterminado":
        onu = unctad = "Indeterminado"
    else:
        norte_onu = reg in ("Europa", "América do Norte") or sub == "Austrália e Nova Zelândia" or p["pais"] in NORTE_EXTRA_ONU
        norte_unc = norte_onu or p["pais"] in NORTE_EXTRA_UNCTAD
        onu = "Norte Global" if norte_onu else "Sul Global"
        unctad = "Norte Global" if norte_unc else "Sul Global"
    linhas.append({
        "pais": p["pais"], "iso3": p["iso3"], "sub_regiao": sub, "regiao": reg,
        "grupo_onu": onu, "grupo_unctad": unctad,
        "palop": "Sim" if p["pais"] in PALOP else "Não", "cplp": "Sim" if p["pais"] in CPLP else "Não",
        "ordem_regiao": ORDEM_REGIAO[reg], "ordem_sub_regiao": ORDEM_SUB[sub],
    })
pd.DataFrame(linhas).rename(columns={
    "pais": "País", "iso3": "ISO3", "sub_regiao": "Sub-região", "regiao": "Região", "grupo_onu": "Classificação ONU",
    "grupo_unctad": "Classificação UNCTAD", "palop": "PALOP", "cplp": "CPLP", "ordem_regiao": "Ordem região",
    "ordem_sub_regiao": "Ordem sub-região",
}).to_csv(os.path.join(SAIDA, "dim_pais.csv"), sep=";", index=False, encoding="utf-8")

ordem_grupo = {g["grupo_ocupacional"]: int(g["ordem"]) for g in GRUPOS_OCUP}
prof_dim = (pd.DataFrame(list(PROF.values()))[["profissao", "grupo_ocupacional"]].drop_duplicates("profissao"))
if "Não informado" not in set(prof_dim["profissao"]):
    prof_dim.loc[len(prof_dim)] = ["Não informado", "Não classificado ou não informado"]
prof_dim["ordem_grupo"] = prof_dim["grupo_ocupacional"].map(ordem_grupo)
prof_dim = prof_dim[prof_dim["profissao"].isin(set(fato["profissao"]))]
prof_dim.sort_values(["ordem_grupo", "profissao"]).rename(columns={
    "profissao": "Profissão", "grupo_ocupacional": "Grupo ocupacional", "ordem_grupo": "Ordem grupo"}).to_csv(os.path.join(SAIDA, "dim_profissao.csv"), sep=";",
                                                          index=False, encoding="utf-8")

ufs = [{"UF": k, "Unidade da Federação": v[0], "Região do Brasil": v[1]} for k, v in UF_NOME.items()]
ufs += [{"UF": "EX", "Unidade da Federação": "Exterior", "Região do Brasil": "Exterior / não informado"},
        {"UF": "NI", "Unidade da Federação": "Não informado", "Região do Brasil": "Exterior / não informado"}]
pd.DataFrame(ufs).to_csv(os.path.join(SAIDA, "dim_uf.csv"), sep=";", index=False, encoding="utf-8")

anos = sorted(fato["ano"].unique())
pd.DataFrame([{
    "Ano": int(a),
    "Ano (rótulo)": f"{a} (jan–{PARCIAL[a]})" if a in PARCIAL else str(a),
    "Ano completo": "Não" if a in PARCIAL else "Sim",
    "Recorte da pesquisa": "2016 em diante" if a >= 2016 else "2010–2015",
} for a in anos]).to_csv(os.path.join(SAIDA, "dim_ano.csv"), sep=";", index=False, encoding="utf-8")

pd.DataFrame({"Faixa etária": FAIXAS, "Ordem": range(1, len(FAIXAS) + 1)}).to_csv(
    os.path.join(SAIDA, "dim_faixa_etaria.csv"), sep=";", index=False, encoding="utf-8")

# ---------------------------------------------------------------- conferência
dp = pd.DataFrame(linhas).set_index("pais")
f = fato.join(dp, on="pais")
print("\nConferência (registros por grupo, critério ONU):")
print(f.groupby("grupo_onu")["registros"].sum().map("{:,d}".format).to_string())
print("\nSul Global (ONU) por região:")
print(f[f.grupo_onu == "Sul Global"].groupby("regiao")["registros"].sum().sort_values(ascending=False)
      .map("{:,d}".format).to_string())
print(f"\nTabelas gravadas em {SAIDA}")
