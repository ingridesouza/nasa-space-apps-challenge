"""Popula `science_targets` com achados REAIS e citáveis da campanha de
boxwork da Curiosity (2025), pesquisados em fontes NASA/JPL -- ver
`fonte_url` de cada entrada.

Posições são REAIS (atualizado em 2026-11-13): nenhuma fonte de
notícia publica lat/lon exata do alvo em si (só sol e nome informal),
mas a posição do ROVER naquele sol é pública e oficial via
`MSL_waypoints.json` do MMGIS (https://mars.nasa.gov/mmgis-maps/MSL/Layers/json/MSL_waypoints.json).
Usamos a posição do rover no sol mais próximo de cada observação como
coordenada do alvo -- é uma aproximação de "onde o rover estava", não
o ponto exato do alvo em si (que pode estar a alguns metros de
distância, dentro do alcance do braço robótico), mas é MUITO mais
preciso que o chute de bbox usado antes (corrigia um erro de 13km).

Cobre parcialmente a pendência "medições do Curiosity como pontos" da
feature 01; o conjunto completo de 8-10 alvos (ficha "pokédex") é
trabalho da feature 4 (Victoria), não duplicado aqui.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from connection import init_db

# mesmo bbox de teste do resto do pipeline -- os 3 pontos são
# espalhados dentro dele só pra não ficarem exatamente sobrepostos.
ALVOS = [
    {
        "nome": "Cristas de boxwork — cimentação por sulfato",
        # posição real do rover no sol 4650 (MSL_waypoints.json)
        "lat": -4.80689,
        "lon": 137.37984,
        "mineral_crism": None,
        "classe_ai4mars": None,
        "medicao_curiosity": (
            "Observação de contato confirmou que as cristas de boxwork são fraturas "
            "cimentadas por sulfato de cálcio; o bedrock das depressões entre cristas tem "
            "composição química diferente do resto do Monte Sharp. Sequência exata de "
            "eventos (o que cimentou primeiro) ainda é questão em aberto pela equipe da missão."
        ),
        "nome_iau_usgs": None,
        "confianca": "alta — posição real do rover no sol 4650 (MMGIS), alvo em si pode estar a alguns metros de distância (alcance do braço robótico)",
        "fonte_url": "https://www.jpl.nasa.gov/news/nasas-curiosity-mars-rover-starts-unpacking-boxwork-formations/",
    },
    {
        "nome": "Altadena — furo de perfuração #43",
        # posição real do rover no sol 4560, mais próximo do sol 4564 (MSL_waypoints.json)
        "lat": -4.79985,
        "lon": 137.38354,
        "mineral_crism": None,
        "classe_ai4mars": None,
        "medicao_curiosity": (
            "43º furo de perfuração da missão, dentro da estrutura de boxwork (sol 4564, "
            "8/jun/2025). Amostra em pó entregue ao CheMin e ao SAM; parede do furo e "
            "material residual examinados por ChemCam, Mastcam, APXS e MAHLI."
        ),
        "nome_iau_usgs": None,
        "confianca": "alta — posição real do rover no sol 4560 (mais próximo de 4564 no MMGIS), furo em si a poucos metros de distância",
        "fonte_url": "https://astrobiology.com/2025/06/examining-the-altadena-drill-hole-on-mars.html",
    },
    {
        "nome": "Totoral / Sillar — crista vs. depressão",
        # posição real do rover no sol 4605, dentro da janela 4600-4606 (MSL_waypoints.json)
        "lat": -4.80443,
        "lon": 137.37956,
        "mineral_crism": None,
        "classe_ai4mars": None,
        "medicao_curiosity": (
            "Alvos de ciência de contato (APXS/MAHLI) comparando o bedrock nodular da "
            "borda de uma depressão com o bedrock liso de uma crista próxima, parte da "
            "campanha de caracterização do boxwork (~sol 4600-4606, jul/2025)."
        ),
        "nome_iau_usgs": None,
        "confianca": "alta — posição real do rover no sol 4605 (dentro da janela 4600-4606, MMGIS)",
        "fonte_url": "https://www.spacedaily.com/reports/Curiosity_Rovers_Boxwork_Campaign_Reaches_New_Heights_on_Mount_Sharp_999.html",
    },
]


def main() -> None:
    conn = init_db()

    # idempotente: limpa pelos nomes antes de inserir de novo, pra poder
    # rodar o script mais de uma vez sem duplicar.
    for alvo in ALVOS:
        rows = conn.execute("SELECT id FROM science_targets WHERE nome = ?", (alvo["nome"],)).fetchall()
        for row in rows:
            conn.execute("DELETE FROM science_targets_rtree WHERE id = ?", (row["id"],))
            conn.execute("DELETE FROM science_targets WHERE id = ?", (row["id"],))

    for alvo in ALVOS:
        cursor = conn.execute(
            """
            INSERT INTO science_targets
                (nome, lat, lon, mineral_crism, classe_ai4mars, medicao_curiosity, nome_iau_usgs, confianca, fonte_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                alvo["nome"],
                alvo["lat"],
                alvo["lon"],
                alvo["mineral_crism"],
                alvo["classe_ai4mars"],
                alvo["medicao_curiosity"],
                alvo["nome_iau_usgs"],
                alvo["confianca"],
                alvo["fonte_url"],
            ),
        )
        target_id = cursor.lastrowid
        conn.execute(
            "INSERT INTO science_targets_rtree (id, min_lon, max_lon, min_lat, max_lat) VALUES (?, ?, ?, ?, ?)",
            (target_id, alvo["lon"], alvo["lon"], alvo["lat"], alvo["lat"]),
        )
        print(f"inserido: {alvo['nome']} (id={target_id})")

    conn.commit()
    conn.close()
    print(f"\n{len(ALVOS)} alvos científicos inseridos.")


if __name__ == "__main__":
    main()
