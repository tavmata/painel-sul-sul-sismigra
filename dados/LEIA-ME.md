# Microdados do SISMIGRA

Coloque aqui os arquivos CSV do SISMIGRA baixados do
[Portal de Imigração do OBMigra/MJSP](https://portaldeimigracao.mj.gov.br/) (Dados › Microdados › SISMIGRA).

- Nomes no formato `sismigra_*.csv`, por exemplo `sismigra_2024.csv` ou `sismigra_2019_2020.csv`.
- Ano incompleto: `sismigra_janeiro_<mês>_<ano>.csv` (ex.: `sismigra_janeiro_abril_2026.csv`). O painel
  rotula esse ano como parcial ("2026 (jan–abr)").
- Formato esperado: separador `;`, codificação UTF-8, com as colunas `DATAREGISTRO`, `PAIS_NACIONALIDADE`,
  `PAIS_NASCIMENTO`, `UNIDADE_FED_RESIDENCIA`, `MUNICIPIO_RESIDENCIA`, `SEXO`, `FAIXA_ETARIA` (ou `IDADE`),
  `ESTADO_CIVIL`, `PROFISSAO`, `TIPOLOGIA_AMPAROS` e `CLASSIFICACAO_REVISADA`.

Os CSV desta pasta não vão para o Git (ver `.gitignore`). Depois de copiá-los, rode `python preparar_dados.py`
na raiz do repositório.
