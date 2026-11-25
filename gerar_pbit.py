"""
Gera o modelo do Power BI "Painel_Migracao_Sul-Sul_SISMIGRA.pbit" (modelo de dados + relatório).

O .pbit não carrega dados: ao abrir, o Power BI pede a pasta das tabelas (parâmetro PastaTabelas)
e importa os CSVs gerados por preparar_dados.py. Depois é só salvar como .pbix.

Uso:  python gerar_pbit.py  [pasta_tabelas_padrão]
"""
import json
import os
import sys
import uuid
import zipfile
import hashlib

AQUI = os.path.dirname(os.path.abspath(__file__))
PASTA_PADRAO = sys.argv[1] if len(sys.argv) > 1 else os.path.join(AQUI, "tabelas")
SAIDA = os.path.join(AQUI, "Painel_Migracao_Sul-Sul_SISMIGRA.pbit")
_TEMA_REL = r"WebView2Resources\minerva\SHAREDRESOURCES\BASETHEMES\CY24SU10.JSON"
_PASTAS_PBI = [os.environ.get("PBI_DESKTOP_BIN", ""), r"D:\Program Files\bin",
               r"C:\Program Files\Microsoft Power BI Desktop\bin"]
TEMA_BASE = next((os.path.join(p, _TEMA_REL) for p in _PASTAS_PBI if p and os.path.exists(os.path.join(p, _TEMA_REL))),
                 None)  # tema base que acompanha o Power BI Desktop (defina PBI_DESKTOP_BIN se estiver em outro lugar)
REPORT_VERSION = "5.59"  # o Power BI 2.143 usa 5.64 e atualiza o layout ao abrir


def gid(*parts):
    """GUID determinístico (o arquivo gerado é idêntico a cada execução)."""
    return str(uuid.UUID(hashlib.md5("|".join(parts).encode()).hexdigest()))


def hexname(*parts):
    return hashlib.md5("|".join(parts).encode()).hexdigest()[:20]


# =====================================================================================
# MODELO DE DADOS
# =====================================================================================
TXT, INT = "string", "int64"


def m_csv(arquivo, colunas):
    """Expressão M que lê um CSV das tabelas e tipa as colunas."""
    tipos = ", ".join(
        '{"%s", %s}' % (c, "Int64.Type" if t == INT else "type text") for c, t, *_ in colunas
    )
    return [
        "let",
        '    Pasta = if Text.EndsWith(PastaTabelas, "\\") then PastaTabelas else PastaTabelas & "\\",',
        f'    Fonte = Csv.Document(File.Contents(Pasta & "{arquivo}"), [Delimiter=";", Columns={len(colunas)}, Encoding=65001, QuoteStyle=QuoteStyle.Csv]),',
        "    Cabecalhos = Table.PromoteHeaders(Fonte, [PromoteAllScalars=true]),",
        f"    Tipos = Table.TransformColumnTypes(Cabecalhos, {{{tipos}}})",
        "in",
        "    Tipos",
    ]


def coluna(tabela, nome, tipo, oculta=False, ordenar_por=None, formato=None, resumo="none"):
    c = {
        "name": nome,
        "dataType": tipo,
        "sourceColumn": nome,
        "lineageTag": gid("col", tabela, nome),
        "summarizeBy": resumo,
        "annotations": [{"name": "SummarizationSetBy", "value": "User"}],
    }
    if oculta:
        c["isHidden"] = True
    if ordenar_por:
        c["sortByColumn"] = ordenar_por
    if formato:
        c["formatString"] = formato
    elif tipo == INT:
        c["formatString"] = "0"
    return c


def tabela_csv(nome, arquivo, colunas, descricao=None):
    t = {
        "name": nome,
        "lineageTag": gid("tab", nome),
        "columns": [coluna(nome, *c) for c in colunas],
        "partitions": [{"name": nome, "mode": "import", "source": {"type": "m", "expression": m_csv(arquivo, colunas)}}],
        "annotations": [{"name": "PBI_ResultType", "value": "Table"}],
    }
    if descricao:
        t["description"] = descricao
    return t


T_REGISTROS = tabela_csv("Registros", "fato_registros.csv", [
    ("Ano", INT, True),
    ("País", TXT, True),
    ("Fonte do país", TXT),
    ("UF", TXT, True),
    ("Município (UF)", TXT),
    ("Sexo", TXT),
    ("Faixa etária", TXT, True),
    ("Estado civil", TXT),
    ("Profissão", TXT, True),
    ("Tipologia de amparo", TXT),
    ("Classificação do registro", TXT),
    ("Quantidade", INT, True, None, "#,0", "sum"),
], "Registros do SISMIGRA agregados (uma linha por combinação de atributos; 'Quantidade' = nº de registros).")
T_PAIS = tabela_csv("País", "dim_pais.csv", [
    ("País", TXT),
    ("ISO3", TXT),
    ("Sub-região", TXT, False, "Ordem sub-região"),
    ("Região", TXT, False, "Ordem região"),
    ("Classificação ONU", TXT),
    ("Classificação UNCTAD", TXT),
    ("PALOP", TXT),
    ("CPLP", TXT),
    ("Ordem região", INT, True),
    ("Ordem sub-região", INT, True),
], "País de referência (nacionalidade; em 2017, país de nascimento), com sub-regiões M49 e critérios de Sul Global.")
T_PROF = tabela_csv("Profissão", "dim_profissao.csv", [
    ("Profissão", TXT),
    ("Grupo ocupacional", TXT, False, "Ordem grupo"),
    ("Ordem grupo", INT, True),
])
T_UF = tabela_csv("UF", "dim_uf.csv", [
    ("UF", TXT),
    ("Unidade da Federação", TXT),
    ("Região do Brasil", TXT),
])
T_ANO = tabela_csv("Ano", "dim_ano.csv", [
    ("Ano", INT, False, None, "0"),
    ("Ano (rótulo)", TXT, False, "Ano"),
    ("Ano completo", TXT),
    ("Recorte da pesquisa", TXT),
])
T_FAIXA = tabela_csv("Faixa etária", "dim_faixa_etaria.csv", [
    ("Faixa etária", TXT, False, "Ordem"),
    ("Ordem", INT, True),
])

T_CRITERIO = {
    "name": "Critério Sul Global",
    "lineageTag": gid("tab", "criterio"),
    "description": "Tabela desconectada: escolhe qual critério define o Sul Global nas medidas.",
    "columns": [
        coluna("Critério Sul Global", "Critério", TXT, ordenar_por="Ordem"),
        coluna("Critério Sul Global", "Código", TXT, oculta=True),
        coluna("Critério Sul Global", "Ordem", INT, oculta=True),
    ],
    "partitions": [{
        "name": "Critério Sul Global", "mode": "import",
        "source": {"type": "m", "expression": [
            "let",
            "    Fonte = #table(",
            "        type table [Critério = text, Código = text, Ordem = Int64.Type],",
            '        {{"ONU/DESA – regiões menos desenvolvidas", "ONU", 1},',
            '         {"UNCTAD – economias em desenvolvimento", "UNCTAD", 2}})',
            "in",
            "    Fonte",
        ]},
    }],
    "annotations": [{"name": "PBI_ResultType", "value": "Table"}],
}

# ---------------------------------------------------------------- medidas
N, P, PP = "#,0", "0.0%", "+0.0%;-0.0%;0.0%"
SUL = "[Registros Sul Global]"
AA = "[Registros Ásia e África]"
OCUPADOS = ('{ "Dirigentes, gerentes e proprietários", "Profissionais das ciências e intelectuais", '
            '"Técnicos e profissionais de nível médio", "Apoio administrativo", "Comércio e serviços", '
            '"Cultura, esportes e diversões", "Agropecuária, pesca e extração", '
            '"Indústria, construção e manutenção", "Transporte e navegação", '
            '"Forças armadas, segurança e diplomacia", "Religiosos" }')
QUALIF = '{ "Dirigentes, gerentes e proprietários", "Profissionais das ciências e intelectuais" }'
ACOLHIDA = ('{ "Acolhida humanitária", "Refúgio/asilo", "Acolhida a venezuelanos", '
            '"Solicitação de refúgio (DPRNM)" }')


def pct_tipologia(base, filtro):
    return f"""DIVIDE (
    CALCULATE ( {base}, KEEPFILTERS ( {filtro} ) ),
    {base}
)"""


def pct_mulheres(base):
    return f"""DIVIDE (
    CALCULATE ( {base}, Registros[Sexo] = "Feminino" ),
    CALCULATE ( {base}, Registros[Sexo] IN {{ "Feminino", "Masculino" }} )
)"""


def pct_qualif(base):
    return f"""VAR ocupados =
    CALCULATE ( {base}, KEEPFILTERS ( 'Profissão'[Grupo ocupacional] IN {OCUPADOS} ) )
VAR qualificados =
    CALCULATE ( {base}, KEEPFILTERS ( 'Profissão'[Grupo ocupacional] IN {QUALIF} ) )
RETURN
    DIVIDE ( qualificados, ocupados )"""


def top_n(base, tabela_rank, coluna_escopo, n=15, filtro_extra=None):
    expr = f"CALCULATE ( {base}, KEEPFILTERS ( {filtro_extra} ) )" if filtro_extra else base
    return f"""VAR valor = {expr}
VAR posicao =
    RANKX ( ALLSELECTED ( {tabela_rank} ), {expr}, , DESC )
RETURN
    IF ( ISINSCOPE ( {coluna_escopo} ) && valor > 0 && posicao <= {n}, valor )"""


def principal(base):
    return f"""VAR topo =
    TOPN ( 1, FILTER ( VALUES ( 'País'[País] ), {base} > 0 ), {base}, DESC )
RETURN
    CONCATENATEX ( topo, 'País'[País], ", " )"""


MEDIDAS = [
    # (pasta, nome, expressão, formato, descrição)
    ("1. Base", "Total de registros", "SUM ( Registros[Quantidade] )", N,
     "Registros no SISMIGRA no contexto atual, de todas as origens."),
    ("1. Base", "Critério selecionado", "SELECTEDVALUE ( 'Critério Sul Global'[Código], \"ONU\" )", None,
     "Código do critério de Sul Global em uso (ONU por padrão)."),
    ("1. Base", "Critério em uso",
     "SELECTEDVALUE ( 'Critério Sul Global'[Critério], \"ONU/DESA – regiões menos desenvolvidas\" )", None,
     "Nome do critério de Sul Global em uso."),
    ("1. Base", "Registros Sul Global", """VAR criterio = [Critério selecionado]
RETURN
    IF (
        criterio = "UNCTAD",
        CALCULATE ( [Total de registros], KEEPFILTERS ( 'País'[Classificação UNCTAD] = "Sul Global" ) ),
        CALCULATE ( [Total de registros], KEEPFILTERS ( 'País'[Classificação ONU] = "Sul Global" ) )
    )""", N, "Registros de migrantes com origem no Sul Global (migração Sul-Sul para o Brasil), pelo critério escolhido."),
    ("1. Base", "Registros Norte Global", """VAR criterio = [Critério selecionado]
RETURN
    IF (
        criterio = "UNCTAD",
        CALCULATE ( [Total de registros], KEEPFILTERS ( 'País'[Classificação UNCTAD] = "Norte Global" ) ),
        CALCULATE ( [Total de registros], KEEPFILTERS ( 'País'[Classificação ONU] = "Norte Global" ) )
    )""", N, "Registros de migrantes com origem no Norte Global, pelo critério escolhido."),
    ("1. Base", "Registros (todas as origens)", "CALCULATE ( [Total de registros], REMOVEFILTERS ( 'País' ) )", N,
     "Total de registros ignorando filtros de país/região (denominador das participações)."),
    ("2. Sul Global", "% Sul Global no total", f"DIVIDE ( {SUL}, [Registros (todas as origens)] )", P,
     "Participação do Sul Global (ou da seleção de países) no total de registros de imigrantes."),
    ("2. Sul Global", "Participação no Sul Global",
     f"DIVIDE ( {SUL}, CALCULATE ( {SUL}, ALLSELECTED ( 'País' ) ) )", P,
     "Participação da linha no total do Sul Global selecionado."),
    ("2. Sul Global", "Países de origem (Sul Global)",
     f"COUNTROWS ( FILTER ( VALUES ( 'País'[País] ), {SUL} > 0 ) )", N, "Número de países do Sul Global com registros."),
    ("2. Sul Global", "Principal origem (Sul Global)", principal(SUL), None, "País do Sul Global com mais registros."),
    ("2. Sul Global", "Participação da principal origem", f"""VAR topo =
    TOPN ( 1, FILTER ( VALUES ( 'País'[País] ), {SUL} > 0 ), {SUL}, DESC )
RETURN
    DIVIDE ( SUMX ( topo, {SUL} ), {SUL} )""", P, "Peso do principal país no total do Sul Global."),
    ("2. Sul Global", "Variação anual (Sul Global)", f"""VAR anoAtual = MAX ( 'Ano'[Ano] )
VAR anterior =
    CALCULATE ( {SUL}, REMOVEFILTERS ( 'Ano' ), 'Ano'[Ano] = anoAtual - 1 )
RETURN
    IF ( HASONEVALUE ( 'Ano'[Ano] ) && NOT ISBLANK ( anterior ), DIVIDE ( {SUL} - anterior, anterior ) )""", PP,
     "Variação em relação ao ano anterior (use com o ano no eixo ou na linha)."),
    ("2. Sul Global", "% mulheres (Sul Global)", pct_mulheres(SUL), P,
     "Mulheres entre os registros com sexo informado."),
    ("2. Sul Global", "% trabalho/investimentos (Sul Global)",
     pct_tipologia(SUL, 'Registros[Tipologia de amparo] = "Trabalho/investimentos"'), P,
     "Registros com amparo de trabalho ou investimentos."),
    ("2. Sul Global", "% acolhida humanitária e refúgio (Sul Global)",
     pct_tipologia(SUL, f"Registros[Tipologia de amparo] IN {ACOLHIDA}"), P,
     "Registros com amparo de acolhida humanitária, acolhida a venezuelanos, refúgio/asilo ou solicitação de "
     "refúgio (documento provisório, Decreto 9.277/2018)."),
    ("2. Sul Global", "% dirigentes e profissionais (Sul Global)", pct_qualif(SUL), P,
     "Dirigentes/gerentes e profissionais das ciências e intelectuais, entre os registros com ocupação "
     "declarada no mercado de trabalho (exclui estudantes, fora da força de trabalho e não classificados)."),
    ("2. Sul Global", "Distribuição por tipologia (%)",
     f"DIVIDE ( {SUL}, CALCULATE ( {SUL}, ALLSELECTED ( Registros[Tipologia de amparo] ) ) )", P,
     "Em matrizes: participação de cada tipologia de amparo no total da origem (coluna)."),
    ("3. Rankings", "Sul Global – top 10 países", top_n(SUL, "'País'", "'País'[País]", 10), N,
     "Registros do Sul Global nos 10 países com mais registros (demais ficam em branco)."),
    ("3. Rankings", "Sul Global – top 15 países", top_n(SUL, "'País'", "'País'[País]"), N,
     "Registros do Sul Global nos 15 países com mais registros (demais ficam em branco)."),
    ("3. Rankings", "Sul Global – top 15 municípios",
     top_n(SUL, "Registros[Município (UF)]", "Registros[Município (UF)]",
           filtro_extra='Registros[Município (UF)] <> "Não informado"'), N,
     "Registros do Sul Global nos 15 municípios de residência com mais registros (exclui não informado)."),
    ("3. Rankings", "Sul Global – top 15 profissões", top_n(SUL, "'Profissão'", "'Profissão'[Profissão]"), N,
     "Registros do Sul Global nas 15 profissões declaradas mais frequentes."),
    ("3. Rankings", "Participação (top 15 profissões)", f"""IF (
    NOT ISBLANK ( [Sul Global – top 15 profissões] ),
    DIVIDE ( {SUL}, CALCULATE ( {SUL}, ALLSELECTED ( 'Profissão' ) ) )
)""", P, "Peso da profissão no total do Sul Global (só para as 15 primeiras)."),
    ("4. Ásia e África", "Registros Ásia e África",
     "CALCULATE ( [Total de registros], KEEPFILTERS ( 'País'[Região] IN { \"Ásia\", \"África\" } ) )", N,
     "Registros de todos os países asiáticos e africanos, sem aplicar o critério de Sul Global "
     "(inclui Japão, Coreia do Sul, Israel e Chipre, para comparação)."),
    ("4. Ásia e África", "% mulheres (Ásia e África)", pct_mulheres(AA), P, None),
    ("4. Ásia e África", "% trabalho/investimentos (Ásia e África)",
     pct_tipologia(AA, 'Registros[Tipologia de amparo] = "Trabalho/investimentos"'), P, None),
    ("4. Ásia e África", "% reunião familiar (Ásia e África)",
     pct_tipologia(AA, 'Registros[Tipologia de amparo] = "Reunião familiar"'), P, None),
    ("4. Ásia e África", "% acolhida humanitária e refúgio (Ásia e África)",
     pct_tipologia(AA, f"Registros[Tipologia de amparo] IN {ACOLHIDA}"), P, None),
    ("4. Ásia e África", "% dirigentes e profissionais (Ásia e África)", pct_qualif(AA), P,
     "Entre os registros com ocupação declarada no mercado de trabalho."),
    ("4. Ásia e África", "Ásia e África – top 10 países", top_n(AA, "'País'", "'País'[País]", 10), N, None),
    ("4. Ásia e África", "Distribuição por grupo ocupacional (%)",
     f"DIVIDE ( {AA}, CALCULATE ( {AA}, ALLSELECTED ( 'Profissão' ) ) )", P,
     "Em matrizes: participação de cada grupo ocupacional no total da sub-região (coluna). "
     "Usa a tabela Profissão inteira porque o grupo é ordenado pela coluna oculta 'Ordem grupo'."),
]

T_MEDIDAS = {
    "name": "Medidas",
    "lineageTag": gid("tab", "medidas"),
    "columns": [coluna("Medidas", "Coluna", TXT, oculta=True)],
    "partitions": [{"name": "Medidas", "mode": "import", "source": {"type": "m", "expression": [
        "let", "    Fonte = #table(type table [Coluna = text], {})", "in", "    Fonte"]}}],
    "measures": [],
    "annotations": [{"name": "PBI_ResultType", "value": "Table"}],
}
for pasta, nome, expr, fmt, desc in MEDIDAS:
    m = {"name": nome, "expression": expr.split("\n"), "displayFolder": pasta, "lineageTag": gid("med", nome)}
    if fmt:
        m["formatString"] = fmt
    if desc:
        m["description"] = desc
    T_MEDIDAS["measures"].append(m)


def rel(de_tab, de_col, para_tab, para_col):
    return {"name": gid("rel", de_tab, de_col), "fromTable": de_tab, "fromColumn": de_col,
            "toTable": para_tab, "toColumn": para_col}


TABELAS = [T_REGISTROS, T_PAIS, T_PROF, T_UF, T_ANO, T_FAIXA, T_CRITERIO, T_MEDIDAS]
MODELO = {
    "name": "Painel Sul-Sul SISMIGRA",
    "compatibilityLevel": 1550,
    "model": {
        "culture": "pt-BR",
        "dataAccessOptions": {"legacyRedirects": True, "returnErrorValuesAsNull": True},
        "defaultPowerBIDataSourceVersion": "powerBI_V3",
        "sourceQueryCulture": "pt-BR",
        "tables": TABELAS,
        "relationships": [
            rel("Registros", "País", "País", "País"),
            rel("Registros", "Profissão", "Profissão", "Profissão"),
            rel("Registros", "UF", "UF", "UF"),
            rel("Registros", "Ano", "Ano", "Ano"),
            rel("Registros", "Faixa etária", "Faixa etária", "Faixa etária"),
        ],
        "expressions": [{
            "name": "PastaTabelas",
            "kind": "m",
            "description": "Pasta com os CSVs gerados por preparar_dados.py (dados\\powerbi\\tabelas).",
            "expression": '"%s" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]'
                          % PASTA_PADRAO.replace('"', '""'),
            "lineageTag": gid("expr", "PastaTabelas"),
            "annotations": [{"name": "PBI_ResultType", "value": "Text"}],
        }],
        "annotations": [
            {"name": "PBI_QueryOrder", "value": json.dumps(["PastaTabelas"] + [t["name"] for t in TABELAS],
                                                           ensure_ascii=False)},
            {"name": "__PBI_TimeIntelligenceEnabled", "value": "0"},
            {"name": "PBIDesktopVersion", "value": "2.143.1378.0 (25.05)"},
        ],
    },
}

# =====================================================================================
# RELATÓRIO (Report/Layout)
# =====================================================================================
TABELAS_POR_NOME = {t["name"]: t for t in TABELAS}
MEDIDAS_NOMES = {m[1] for m in MEDIDAS}


def lit(v):
    if isinstance(v, bool):
        s = "true" if v else "false"
    elif isinstance(v, (int, float)):
        s = f"{float(v):g}D"
    else:
        s = "'" + str(v).replace("'", "''") + "'"
    return {"expr": {"Literal": {"Value": s}}}


def props(**kw):
    return [{"properties": {k: (v if isinstance(v, dict) else lit(v)) for k, v in kw.items()}}]


class Campo:
    """'Tabela[Coluna]' ou '[Medida]'."""

    def __init__(self, spec):
        if spec.startswith("["):
            self.tabela, self.prop, self.medida = "Medidas", spec[1:-1], True
            assert self.prop in MEDIDAS_NOMES, f"medida inexistente: {spec}"
        else:
            tab, col = spec[:-1].split("[")
            self.tabela, self.prop, self.medida = tab.strip("'"), col, False
            cols = [c["name"] for c in TABELAS_POR_NOME[self.tabela]["columns"]]
            assert self.prop in cols, f"coluna inexistente: {spec}"
        self.ref = f"{self.tabela}.{self.prop}"


class Consulta:
    def __init__(self):
        self.aliases = {}

    def alias(self, tabela):
        if tabela not in self.aliases:
            base = "".join(ch for ch in tabela.lower() if ch.isalpha())[:1] or "t"
            a, i = base, 1
            while a in self.aliases.values():
                i += 1
                a = f"{base}{i}"
            self.aliases[tabela] = a
        return self.aliases[tabela]

    def expr(self, c: Campo):
        kind = "Measure" if c.medida else "Column"
        return {kind: {"Expression": {"SourceRef": {"Source": self.alias(c.tabela)}}, "Property": c.prop}}

    def select(self, c: Campo):
        d = self.expr(c)
        d["Name"] = c.ref
        d["NativeReferenceName"] = c.prop
        return d

    def froms(self):
        return [{"Name": a, "Entity": t, "Type": 0} for t, a in self.aliases.items()]


def visual(tipo, x, y, w, h, papeis, titulo=None, ordem=None, objetos=None, vc=None, nomes=None, sync=None,
           pagina=""):
    q = Consulta()
    selects, vistos, projections = [], set(), {}
    for papel, specs in papeis.items():
        projections[papel] = []
        for i, spec in enumerate(specs):
            c = Campo(spec)
            if c.ref not in vistos:
                selects.append(q.select(c))
                vistos.add(c.ref)
            item = {"queryRef": c.ref}
            if papel in ("Category", "Rows", "Values", "Group") and i == 0 and tipo not in ("tableEx", "card"):
                item["active"] = True
            projections[papel].append(item)
    proto = {"Version": 2, "From": None, "Select": selects}
    if ordem:
        spec, direcao = ordem
        c = Campo(spec)
        proto["OrderBy"] = [{"Direction": 2 if direcao == "desc" else 1, "Expression": q.expr(c)}]
    proto["From"] = q.froms()
    sv = {"visualType": tipo, "projections": projections, "prototypeQuery": proto, "drillFilterOtherVisuals": True}
    if nomes:
        sv["columnProperties"] = {Campo(k).ref: {"displayName": v} for k, v in nomes.items()}
    if objetos:
        sv["objects"] = objetos
    vco = dict(vc or {})
    if titulo:
        vco["title"] = props(show=True, text=titulo)
    if vco:
        sv["vcObjects"] = vco
    if sync:
        sv["syncGroup"] = {"groupName": sync, "fieldChanges": True, "filterChanges": True}
    return container(pagina + tipo + str((x, y)), x, y, w, h, sv)


def container(chave, x, y, w, h, single_visual):
    nome = hexname("vis", chave)
    cfg = {"name": nome,
           "layouts": [{"id": 0, "position": {"x": x, "y": y, "z": 0, "width": w, "height": h}}],
           "singleVisual": single_visual}
    return {"x": x, "y": y, "z": 0, "width": w, "height": h,
            "config": json.dumps(cfg, ensure_ascii=False), "filters": "[]"}


INK, INK2, INK3 = "#0b0b0b", "#52514e", "#8a8984"


def texto(chave, x, y, w, h, paragrafos):
    """paragrafos: lista de listas de trechos (texto, tamanho_pt, negrito, cor); [] = linha em branco."""
    pars = []
    for trechos in paragrafos:
        runs = []
        for t, tam, neg, cor in (trechos or [("", 6, False, INK2)]):
            estilo = {"fontSize": f"{tam}pt", "color": cor}
            if neg:
                estilo["fontWeight"] = "bold"
            runs.append({"value": t, "textStyle": estilo})
        pars.append({"textRuns": runs})
    sv = {"visualType": "textbox", "drillFilterOtherVisuals": True,
          "objects": {"general": [{"properties": {"paragraphs": pars}}]},
          "vcObjects": {"background": props(show=False), "border": props(show=False)}}
    return container("txt" + chave, x, y, w, h, sv)


LARGURA_SLICER = {"ano": 200, "criterio": 230, "regiao": 180, "pais": 180}


def cabecalho(pag, titulo, subtitulo, slicers):
    vs = []
    x = 1264
    for s in reversed(slicers):
        w = LARGURA_SLICER[s]
        x -= w
        vs.append(slicer(pag, s, x, 8, w, 64))
        x -= 10
    vs.insert(0, texto(pag + "titulo", 16, 6, x - 16, 70, [[(titulo, 18, True, INK)], [(subtitulo, 9, False, INK2)]]))
    return vs


CRITERIO_PADRAO = "ONU/DESA – regiões menos desenvolvidas"


def slicer(pag, tipo, x, y, w, h):
    campo = {"ano": "Ano[Ano]", "criterio": "'Critério Sul Global'[Critério]", "regiao": "País[Região]",
             "pais": "País[País]"}[tipo]
    modo = "Between" if tipo == "ano" else "Dropdown"
    obj = {"data": props(mode=modo)}
    if tipo == "criterio":
        obj["selection"] = props(singleSelect=True)
        obj["general"] = [{"properties": {"filter": {"filter": {
            "Version": 2,
            "From": [{"Name": "c", "Entity": "Critério Sul Global", "Type": 0}],
            "Where": [{"Condition": {"In": {
                "Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "c"}}, "Property": "Critério"}}],
                "Values": [[{"Literal": {"Value": "'" + CRITERIO_PADRAO + "'"}}]],
            }}}],
        }}}}]
    titulos = {"ano": "Ano de registro", "criterio": "Critério de Sul Global",
               "regiao": "Região de origem", "pais": "País de origem"}
    return visual("slicer", x, y, w, h, {"Values": [campo]}, objetos=obj, sync=tipo, pagina=pag,
                  nomes={campo: titulos[tipo]})


def card(pag, x, y, w, h, medida, rotulo):
    return visual("card", x, y, w, h, {"Values": [medida]}, pagina=pag, nomes={medida: rotulo},
                  objetos={"labels": props(fontSize=20, labelDisplayUnits=1),
                           "categoryLabels": props(show=True, fontSize=9)})


CORES_REGIAO = {"América Latina e Caribe": "#2a78d6", "Ásia": "#eb6834", "África": "#1baf7a", "Oceania": "#eda100",
                "Europa": "#6250d6", "América do Norte": "#e87ba4", "Indeterminado": "#b5b4ae"}
CORES_SEXO = {"Feminino": "#2a78d6", "Masculino": "#eb6834", "Não informado": "#b5b4ae"}


def cores(spec, mapa):
    """Cor fixa por valor da série (a cor acompanha a entidade em todos os visuais)."""
    c = Campo(spec)
    return [{
        "properties": {"fill": {"solid": {"color": lit(cor)}}},
        "selector": {"data": [{"scopeId": {"Comparison": {
            "ComparisonKind": 0,
            "Left": {"Column": {"Expression": {"SourceRef": {"Entity": c.tabela}}, "Property": c.prop}},
            "Right": {"Literal": {"Value": "'" + valor + "'"}},
        }}}]},
    } for valor, cor in mapa.items()]


def eixos(rotulos, margem=None, titulo_valor=False):
    cat = {"showAxisTitle": False}
    if margem:
        cat["maxMarginFactor"] = margem
    obj = {"categoryAxis": props(**cat)}
    if rotulos:
        obj["valueAxis"] = props(show=False, showAxisTitle=False)
        obj["labels"] = props(show=True, labelDisplayUnits=1, fontSize=8)
    else:
        obj["valueAxis"] = props(showAxisTitle=titulo_valor)
    return obj


def barras(pag, x, y, w, h, categoria, medida, titulo, ordem="desc", rotulos=True, serie=None, tipo="clusteredBarChart",
           nomes=None, margem=40, legenda=None):
    papeis = {"Category": [categoria], "Y": [medida]}
    if serie:
        papeis["Series"] = [serie]
    ordem_spec = (medida, "desc") if ordem == "desc" else (categoria, "asc")
    obj = eixos(rotulos, margem if tipo in ("clusteredBarChart", "hundredPercentStackedBarChart") else None)
    if legenda:
        obj["legend"] = props(show=True, position=legenda, showTitle=False)
    if serie == "Registros[Sexo]":
        obj["dataPoint"] = cores(serie, CORES_SEXO)
    return visual(tipo, x, y, w, h, papeis, titulo=titulo, ordem=ordem_spec, objetos=obj, pagina=pag, nomes=nomes)


def linhas(pag, x, y, w, h, categoria, medidas, titulo, serie=None, multiplos=None, nomes=None):
    papeis = {"Category": [categoria], "Y": medidas}
    if serie:
        papeis["Series"] = [serie]
    if multiplos:
        papeis["Rows"] = [multiplos]
    obj = eixos(False)
    if multiplos:
        obj["smallMultiplesLayout"] = props(rowCount=2, columnCount=6)
    if serie == "País[Região]":
        obj["dataPoint"] = cores(serie, CORES_REGIAO)
    return visual("lineChart", x, y, w, h, papeis, titulo=titulo, ordem=(categoria, "asc"), objetos=obj, pagina=pag,
                  nomes=nomes)


def calor(medida):
    """Formatação condicional (cor de fundo em gradiente, rampa sequencial azul) para matriz."""
    return {
        "properties": {"backColor": {"solid": {"color": {"expr": {"FillRule": {
            "Input": {"Measure": {"Expression": {"SourceRef": {"Entity": "Medidas"}}, "Property": medida}},
            "FillRule": {"linearGradient2": {
                "min": {"color": {"Literal": {"Value": "'#fcfcfb'"}}},
                "max": {"color": {"Literal": {"Value": "'#5598e7'"}}},
                "nullColoringStrategy": {"strategy": {"Literal": {"Value": "'asZero'"}}},
            }},
        }}}}}},
        "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}], "metadata": f"Medidas.{medida}"},
    }


def matriz(pag, x, y, w, h, linhas_, colunas, valores, titulo, nomes=None, heat=None, ordem=None, largura_col=None):
    papeis = {"Rows": linhas_}
    if colunas:
        papeis["Columns"] = colunas
    papeis["Values"] = valores
    obj = {"columnHeaders": props(wordWrap=True)}
    if heat:
        obj["values"] = [calor(heat)]
    if largura_col:
        obj["columnWidth"] = [{"properties": {"value": lit(largura_col)},
                               "selector": {"metadata": Campo(v).ref}} for v in valores]
    return visual("pivotTable", x, y, w, h, papeis, titulo=titulo, objetos=obj, nomes=nomes, pagina=pag, ordem=ordem)


def tabela(pag, x, y, w, h, campos, titulo, ordem=None, nomes=None, totais=True, larguras=None):
    obj = {"columnHeaders": props(wordWrap=True)}
    if larguras:
        obj["columnWidth"] = [{"properties": {"value": lit(v)}, "selector": {"metadata": Campo(k).ref}}
                              for k, v in larguras.items()]
    if not totais:
        obj["total"] = props(totals=False)
    return visual("tableEx", x, y, w, h, {"Values": campos}, titulo=titulo, ordem=ordem, nomes=nomes, pagina=pag,
                  objetos=obj)


def pagina(nome, ordinal, visuais):
    return {
        "name": "ReportSection" + hexname("pag", nome),
        "displayName": nome,
        "filters": "[]",
        "ordinal": ordinal,
        "visualContainers": visuais,
        "config": "{}",
        "displayOption": 1,
        "width": 1280,
        "height": 720,
    }


# ---------------------------------------------------------------- páginas
S = "[Registros Sul Global]"
R = {S: "Registros"}
PAGS = []

p = "p1"
PAGS.append(pagina("Visão geral", 0, cabecalho(p, "Migração Sul-Sul no Brasil",
    "Registros de imigrantes no SISMIGRA com origem no Sul Global · 2010 a abril de 2026",
    ["ano", "criterio", "regiao"]) + [
    card(p, 16, 84, 241, 88, S, "Registros Sul-Sul"),
    card(p, 267, 84, 241, 88, "[% Sul Global no total]", "% do total de registros de imigrantes"),
    card(p, 518, 84, 241, 88, "[Países de origem (Sul Global)]", "Países de origem no Sul Global"),
    card(p, 769, 84, 241, 88, "[Principal origem (Sul Global)]", "Principal origem"),
    card(p, 1020, 84, 244, 88, "[% mulheres (Sul Global)]", "Mulheres (entre sexo informado)"),
    linhas(p, 16, 182, 820, 214, "Ano[Ano (rótulo)]", [S, "[Registros Norte Global]"],
           "Registros por ano – Sul Global e Norte Global (2026: jan–abr)",
           nomes={S: "Sul Global", "[Registros Norte Global]": "Norte Global"}),
    barras(p, 848, 182, 416, 214, "País[Região]", S, "Sul Global por região de origem", nomes=R),
    barras(p, 16, 406, 410, 306, "País[País]", "[Sul Global – top 10 países]", "10 principais países de origem",
           nomes={"[Sul Global – top 10 países]": "Registros"}),
    barras(p, 438, 406, 410, 306, "Registros[Tipologia de amparo]", S, "Tipologia de amparo legal", nomes=R),
    tabela(p, 860, 406, 404, 306, ["País[Região]", S, "[% trabalho/investimentos (Sul Global)]",
                                   "[% acolhida humanitária e refúgio (Sul Global)]"],
           "Indicadores por região", ordem=(S, "desc"),
           nomes={S: "Registros", "[% trabalho/investimentos (Sul Global)]": "% trabalho/ invest.",
                  "[% acolhida humanitária e refúgio (Sul Global)]": "% acolhida/ refúgio"},
           larguras={"País[Região]": 140, S: 78, "[% trabalho/investimentos (Sul Global)]": 72,
                     "[% acolhida humanitária e refúgio (Sul Global)]": 72}),
]))

p = "p2"
PAGS.append(pagina("Origens", 1, cabecalho(p, "Origens da migração Sul-Sul",
    "Regiões e sub-regiões da ONU (M49) e países de nacionalidade",
    ["ano", "criterio", "regiao", "pais"]) + [
    visual("treemap", 16, 84, 620, 300, {"Group": ["País[Região]"], "Details": ["País[Sub-região]"], "Values": [S]},
           titulo="Registros por região e sub-região", ordem=(S, "desc"), pagina=p, nomes=R,
           objetos={"dataPoint": cores("País[Região]", CORES_REGIAO)}),
    linhas(p, 648, 84, 616, 300, "Ano[Ano (rótulo)]", [S], "Evolução anual por região de origem",
           serie="País[Região]", nomes=R),
    matriz(p, 16, 396, 620, 316, ["País[Região]", "País[Sub-região]", "País[País]"], None,
           [S, "[Participação no Sul Global]", "[% mulheres (Sul Global)]", "[% trabalho/investimentos (Sul Global)]",
            "[% acolhida humanitária e refúgio (Sul Global)]"],
           "Região › sub-região › país (clique em + para expandir)", ordem=(S, "desc"),
           nomes={S: "Registros", "[Participação no Sul Global]": "% do Sul Global",
                  "[% mulheres (Sul Global)]": "% mulheres",
                  "[% trabalho/investimentos (Sul Global)]": "% trabalho/ invest.",
                  "[% acolhida humanitária e refúgio (Sul Global)]": "% acolhida/ refúgio"}),
    barras(p, 648, 396, 616, 316, "País[País]", "[Sul Global – top 15 países]", "15 principais países de origem",
           nomes={"[Sul Global – top 15 países]": "Registros"}),
]))

p = "p3"
PAGS.append(pagina("Perfil", 2, cabecalho(p, "Perfil dos migrantes",
    "Sexo, faixa etária, estado civil e profissão declarada no registro",
    ["ano", "criterio", "regiao", "pais"]) + [
    barras(p, 16, 84, 400, 300, "País[Região]", S, "Sexo por região de origem", serie="Registros[Sexo]",
           tipo="hundredPercentStackedBarChart", rotulos=False, nomes=R),
    barras(p, 428, 84, 420, 300, "'Faixa etária'[Faixa etária]", S, "Faixa etária e sexo", ordem="asc",
           serie="Registros[Sexo]", tipo="clusteredColumnChart", rotulos=False, nomes=R),
    barras(p, 860, 84, 404, 300, "Registros[Estado civil]", S, "Estado civil", nomes=R, margem=30),
    barras(p, 16, 396, 540, 316, "'Profissão'[Grupo ocupacional]", S, "Grande grupo ocupacional (classificação própria)",
           nomes=R, margem=45),
    tabela(p, 568, 396, 696, 316, ["'Profissão'[Profissão]", "'Profissão'[Grupo ocupacional]",
                                   "[Sul Global – top 15 profissões]", "[Participação (top 15 profissões)]"],
           "15 profissões declaradas mais frequentes", ordem=("[Sul Global – top 15 profissões]", "desc"),
           nomes={"[Sul Global – top 15 profissões]": "Registros", "[Participação (top 15 profissões)]": "% do total"},
           totais=False),
]))

p = "p4"
D = "[Distribuição por tipologia (%)]"
PAGS.append(pagina("Amparo legal", 3, cabecalho(p, "Amparo legal e tipo de registro",
    "Base legal da autorização (tipologia de amparo) e classificação do registro",
    ["ano", "criterio", "regiao", "pais"]) + [
    barras(p, 16, 84, 400, 300, "Registros[Tipologia de amparo]", S, "Registros por tipologia de amparo", nomes=R,
           margem=45),
    linhas(p, 428, 84, 836, 300, "Ano[Ano]", [S], "Evolução anual de cada tipologia de amparo (2026: jan–abr)",
           multiplos="Registros[Tipologia de amparo]", nomes=R),
    matriz(p, 16, 396, 820, 316, ["Registros[Tipologia de amparo]"], ["País[Região]", "País[Sub-região]"], [D],
           "Tipologia de amparo por região de origem (% da coluna; expanda as colunas para ver sub-regiões)",
           heat="Distribuição por tipologia (%)", nomes={D: "%"}, ordem=(S, "desc")),
    barras(p, 848, 396, 416, 316, "País[Região]", S, "Classificação do registro por região",
           serie="Registros[Classificação do registro]", tipo="hundredPercentStackedBarChart", rotulos=False, nomes=R,
           legenda="Right"),
]))

p = "p5"
PAGS.append(pagina("Destinos no Brasil", 4, cabecalho(p, "Onde residem no Brasil",
    "Unidade da Federação e município de residência informados no registro",
    ["ano", "criterio", "regiao", "pais"]) + [
    barras(p, 16, 84, 360, 628, "UF[Unidade da Federação]", S, "Registros por Unidade da Federação", nomes=R,
           margem=45),
    barras(p, 388, 84, 380, 210, "UF[Região do Brasil]", S, "Registros por região do Brasil", nomes=R),
    barras(p, 388, 306, 380, 406, "Registros[Município (UF)]", "[Sul Global – top 15 municípios]",
           "15 principais municípios de residência", nomes={"[Sul Global – top 15 municípios]": "Registros"},
           margem=45),
    matriz(p, 780, 84, 484, 628, ["UF[Unidade da Federação]"], ["País[Região]"], [S],
           "UF de residência × região de origem", nomes=R, ordem=(S, "desc")),
]))

p = "p6"
AAm = "[Registros Ásia e África]"
G = "[Distribuição por grupo ocupacional (%)]"
PAGS.append(pagina("Ásia e África", 5, cabecalho(p, "Ásia e África em foco",
    "Todos os países das duas regiões, inclusive Japão, Coreia do Sul e Israel",
    ["ano", "regiao", "pais"]) + [
    tabela(p, 16, 84, 884, 292, ["País[Sub-região]", AAm, "[% mulheres (Ásia e África)]",
                                  "[% trabalho/investimentos (Ásia e África)]", "[% reunião familiar (Ásia e África)]",
                                  "[% acolhida humanitária e refúgio (Ásia e África)]",
                                  "[% dirigentes e profissionais (Ásia e África)]"],
           "Indicadores por sub-região", ordem=("País[Sub-região]", "asc"),
           nomes={AAm: "Registros", "[% mulheres (Ásia e África)]": "% mulheres",
                  "[% trabalho/investimentos (Ásia e África)]": "% trabalho/ investimentos",
                  "[% reunião familiar (Ásia e África)]": "% reunião familiar",
                  "[% acolhida humanitária e refúgio (Ásia e África)]": "% acolhida humanitária/ refúgio",
                  "[% dirigentes e profissionais (Ásia e África)]": "% dirigentes e profissionais*"},
           larguras={"País[Sub-região]": 150, AAm: 90, "[% mulheres (Ásia e África)]": 100,
                     "[% trabalho/investimentos (Ásia e África)]": 110, "[% reunião familiar (Ásia e África)]": 110,
                     "[% acolhida humanitária e refúgio (Ásia e África)]": 130,
                     "[% dirigentes e profissionais (Ásia e África)]": 130}),
    barras(p, 912, 84, 352, 292, "País[País]", "[Ásia e África – top 10 países]", "10 principais países",
           nomes={"[Ásia e África – top 10 países]": "Registros"}),
    matriz(p, 16, 388, 1248, 324, ["'Profissão'[Grupo ocupacional]"], ["País[Sub-região]"], [G],
           "Grupo ocupacional por sub-região (% da coluna)",
           heat="Distribuição por grupo ocupacional (%)", nomes={G: "%"}),
]))


def nota(titulo, corpo):
    return [[(titulo + " ", 11, True, INK), (corpo, 11, False, INK2)], []]


NOTAS = [[("Notas metodológicas", 18, True, INK)], []]
NOTAS += nota("Fonte e unidade de análise.",
              "Microdados do SISMIGRA (Sistema de Registro Nacional Migratório, Polícia Federal), arquivos de 2010 a "
              "abril de 2026. Cada linha é um registro de imigrante contado pelo ano de registro: não é número de "
              "pessoas únicas nem fluxo de entrada. 2026 é parcial (janeiro a abril).")
NOTAS += nota("País de referência.",
              "País de nacionalidade. O arquivo de 2017 não traz nacionalidade; para esse ano usa-se o país de "
              "nascimento (nos demais anos os dois coincidem em 97,6% dos registros). O campo CONTINENTE do SISMIGRA "
              "foi descartado por inconsistências; região e sub-região vêm da classificação M49 da ONU.")
NOTAS += nota("Sul Global – critério ONU/DESA (padrão).",
              "Regiões menos desenvolvidas: todos os países, exceto Europa, América do Norte (EUA, Canadá, Bermudas, "
              "Groenlândia), Austrália, Nova Zelândia e Japão.")
NOTAS += nota("Sul Global – critério UNCTAD.",
              "Economias em desenvolvimento: como o anterior, excluindo também Israel, Coreia do Sul e Chipre. "
              "Troque o critério no seletor do topo das páginas.")
NOTAS += nota("Página Ásia e África.",
              "Mostra todos os países asiáticos e africanos, independentemente do critério, para comparar a Ásia "
              "Oriental (China, Japão, Coreias, Taiwan) com o Sul e o Sudeste Asiático e com a África.")
NOTAS += nota("Solicitação de refúgio (DPRNM).",
              "O SISMIGRA rotula como “Não aplicável” os registros com amparo 290 (art. 2º do Decreto 9.277/2018), "
              "isto é, o Documento Provisório de Registro Nacional Migratório de solicitantes de refúgio. Aqui eles "
              "aparecem como “Solicitação de refúgio (DPRNM)” e entram no indicador de acolhida humanitária e refúgio.")
NOTAS += nota("Profissões e grupos ocupacionais.",
              "As grafias do SISMIGRA (inclusive as truncadas do arquivo 2010–2017) foram padronizadas em 95 "
              "profissões e reunidas em 14 grandes grupos, em classificação própria inspirada nos grandes grupos da "
              "CBO/ISCO. O indicador “% dirigentes e profissionais*” é calculado sobre os registros com ocupação "
              "declarada no mercado de trabalho (exclui estudantes, menores, sem ocupação, aposentados, dependentes "
              "e não classificados).")
NOTAS += nota("Atualização e edição.",
              "As classificações ficam na pasta referencias (CSV editáveis). Depois de editar ou incluir "
              "novos arquivos do SISMIGRA, rode preparar_dados.py e clique em Atualizar no Power BI.")
NOTAS += nota("Código aberto.",
              "Scripts, classificações e este painel estão em github.com/tavmata/painel-sul-sul-sismigra "
              "(código sob licença MIT; tabelas, painel e textos sob CC BY 4.0). Ao usar, cite o painel e o SISMIGRA.")
PAGS.append(pagina("Notas metodológicas", 6, [texto("notas", 16, 16, 1248, 690, NOTAS)]))

TEMA_NOME = "TemaSulSul"
TEMA = {
    "name": "Sul-Sul",
    "dataColors": ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"],
    "foreground": INK,
    "foregroundNeutralSecondary": INK2,
    "foregroundNeutralTertiary": INK3,
    "background": "#fcfcfb",
    "backgroundLight": "#f3f2ef",
    "backgroundNeutral": "#e6e5e0",
    "tableAccent": "#2a78d6",
    "maximum": "#104281",
    "center": "#86b6ef",
    "minimum": "#eef5fd",
    "good": "#0ca30c",
    "neutral": "#fab219",
    "bad": "#d03b3b",
    "textClasses": {
        "callout": {"fontSize": 22, "fontFace": "Segoe UI Semibold", "color": INK},
        "title": {"fontSize": 11, "fontFace": "Segoe UI Semibold", "color": INK},
        "header": {"fontSize": 10, "fontFace": "Segoe UI Semibold", "color": INK},
        "label": {"fontSize": 9, "fontFace": "Segoe UI", "color": INK2},
    },
    "visualStyles": {
        "page": {"*": {"background": [{"color": {"solid": {"color": "#f0efec"}}, "transparency": 0}]}},
        "*": {"*": {
            "background": [{"show": True, "color": {"solid": {"color": "#fcfcfb"}}, "transparency": 0}],
            "border": [{"show": True, "color": {"solid": {"color": "#e6e5e0"}}, "radius": 6}],
        }},
    },
}

LAYOUT_CONFIG = {
    "version": REPORT_VERSION,
    "themeCollection": {
        "baseTheme": {"name": "CY24SU10", "version": REPORT_VERSION, "type": 2},
        "customTheme": {"name": TEMA_NOME + ".json", "version": REPORT_VERSION, "type": 1},
    },
    "activeSectionIndex": 0,
    "defaultDrillFilterOtherVisuals": True,
    "linguisticSchemaSyncVersion": 0,
    "settings": {"useNewFilterPaneExperience": True, "allowChangeFilterTypes": True,
                 "useStylableVisualContainerHeader": True, "exportDataMode": 1},
    "objects": {"outspacePane": [{"properties": {"expanded": lit(False)}}]},
}

LAYOUT = {
    "id": 0,
    "resourcePackages": [
        {"resourcePackage": {"name": "SharedResources", "type": 2, "disabled": False,
                             "items": [{"type": 202, "path": "BaseThemes/CY24SU10.json", "name": "CY24SU10"}]}},
        {"resourcePackage": {"name": "RegisteredResources", "type": 1, "disabled": False,
                             "items": [{"type": 201, "path": TEMA_NOME + ".json", "name": TEMA_NOME + ".json"}]}},
    ],
    "sections": PAGS,
    "config": json.dumps(LAYOUT_CONFIG, ensure_ascii=False),
    "layoutOptimization": 0,
}

# =====================================================================================
# EMPACOTAMENTO
# =====================================================================================
CONTENT_TYPES = (
    '<?xml version="1.0" encoding="utf-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="json" ContentType="" />'
    '<Override PartName="/Version" ContentType="" />'
    '<Override PartName="/DataModelSchema" ContentType="" />'
    '<Override PartName="/DiagramLayout" ContentType="" />'
    '<Override PartName="/Report/Layout" ContentType="" />'
    '<Override PartName="/Settings" ContentType="" />'
    '<Override PartName="/Metadata" ContentType="" />'
    "</Types>"
)
DIAGRAM = {
    "version": "1.1.0",
    "diagrams": [{"ordinal": 0, "scrollPosition": {"x": 0, "y": 0}, "nodes": [], "name": "Todas as tabelas",
                  "zoomValue": 100, "pinKeyFieldsToTop": False, "showExtraHeaderInfo": False,
                  "hideKeyFieldsWhenCollapsed": False, "tablesLocked": False}],
    "selectedDiagram": "Todas as tabelas",
    "defaultDiagram": "Todas as tabelas",
}
SETTINGS = {"Version": 4, "ReportSettings": {},
            "QueriesSettings": {"TypeDetectionEnabled": True, "RelationshipImportEnabled": False,
                                "Version": "2.143.1378.0"}}
METADATA = {"Version": 5, "AutoCreatedRelationships": [], "CreatedFrom": "Desktop", "CreatedFromRelease": "2025.05"}


def u16(obj):
    s = obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False)
    return s.encode("utf-16-le")


def main():
    if not TEMA_BASE:
        raise SystemExit("Tema base CY24SU10 não encontrado: defina PBI_DESKTOP_BIN com a pasta bin do Power BI Desktop.")
    with open(TEMA_BASE, "rb") as f:
        tema_base = f.read()
    with zipfile.ZipFile(SAIDA, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES.encode("utf-8"))
        z.writestr("Version", u16("1.28"))
        z.writestr("DataModelSchema", u16(MODELO))
        z.writestr("DiagramLayout", u16(DIAGRAM))
        z.writestr("Report/Layout", u16(LAYOUT))
        z.writestr("Report/StaticResources/SharedResources/BaseThemes/CY24SU10.json", tema_base)
        z.writestr(f"Report/StaticResources/RegisteredResources/{TEMA_NOME}.json",
                   json.dumps(TEMA, ensure_ascii=False, indent=2).encode("utf-8"))
        z.writestr("Settings", u16(SETTINGS))
        z.writestr("Metadata", u16(METADATA))
    n_vis = sum(len(s["visualContainers"]) for s in PAGS)
    print(f"Gerado: {SAIDA}\n  {len(PAGS)} páginas, {n_vis} visuais, {len(MEDIDAS)} medidas; pasta padrão: {PASTA_PADRAO}")


if __name__ == "__main__":
    main()
