# openfootball team-name fragmentation & canonicalization

Evidence-first: the raw-name inventory below was generated from the pinned
packs BEFORE the per-league canonicalizers were written; the mapping encodes
the human adjudication of that evidence, and this script re-proves it on
every run. Properties proved: (1) canonicalization is injective within every
season; (2) every adjudicated same-club drift pair merges (no cross-season
fragmentation); (3) adjudicated distinct clubs never merge — including pairs
that never coexisted (AC Ajaccio vs Gazélec Ajaccio, Paris FC vs
Paris Saint-Germain, Chievo Verona vs Hellas Verona); (4) per-league distinct
club counts match the adjudicated evidence.

Judgment call, stated openly: `Parma FC` (to 2014-15) and `Parma Calcio 1913`
(2018-19 on) are the 2015 bankruptcy/refoundation of the same sporting
identity and are merged as `Parma`, matching common football-statistical
practice. A ratings model is barely affected either way — the club was out
of Serie A for three seasons in between.

## English Premier League (`en.1`)

- raw names: 54 | canonical clubs: 41 (adjudicated: 41)
- multi-variant normalization clusters: 13

| Raw name | Seasons | Canonical |
|---|---|---|
| AFC Bournemouth ⟶ | 2015-16 → 2025-26 (9) | Bournemouth |
| Arsenal FC ⟶ | 2010-11 → 2025-26 (16) | Arsenal |
| Aston Villa | 2010-11 → 2019-20 (7) | Aston Villa |
| Aston Villa FC ⟶ | 2020-21 → 2025-26 (6) | Aston Villa |
| Birmingham City | 2010-11 → 2010-11 (1) | Birmingham City |
| Blackburn Rovers | 2010-11 → 2011-12 (2) | Blackburn Rovers |
| Blackpool FC ⟶ | 2010-11 → 2010-11 (1) | Blackpool |
| Bolton Wanderers | 2010-11 → 2011-12 (2) | Bolton Wanderers |
| Brentford FC ⟶ | 2021-22 → 2025-26 (5) | Brentford |
| Brighton & Hove Albion | 2017-18 → 2019-20 (3) | Brighton & Hove Albion |
| Brighton & Hove Albion FC ⟶ | 2020-21 → 2025-26 (6) | Brighton & Hove Albion |
| Burnley FC ⟶ | 2014-15 → 2025-26 (9) | Burnley |
| Cardiff City | 2013-14 → 2018-19 (2) | Cardiff City |
| Chelsea FC ⟶ | 2010-11 → 2025-26 (16) | Chelsea |
| Crystal Palace | 2013-14 → 2019-20 (7) | Crystal Palace |
| Crystal Palace FC ⟶ | 2020-21 → 2025-26 (6) | Crystal Palace |
| Everton FC ⟶ | 2010-11 → 2025-26 (16) | Everton |
| Fulham FC ⟶ | 2010-11 → 2025-26 (10) | Fulham |
| Huddersfield Town | 2017-18 → 2018-19 (2) | Huddersfield Town |
| Hull City | 2013-14 → 2016-17 (3) | Hull City |
| Ipswich Town FC ⟶ | 2024-25 → 2024-25 (1) | Ipswich Town |
| Leeds United FC ⟶ | 2020-21 → 2025-26 (4) | Leeds United |
| Leicester City | 2014-15 → 2019-20 (6) | Leicester City |
| Leicester City FC ⟶ | 2020-21 → 2024-25 (4) | Leicester City |
| Liverpool FC ⟶ | 2010-11 → 2025-26 (16) | Liverpool |
| Luton Town FC ⟶ | 2023-24 → 2023-24 (1) | Luton Town |
| Manchester City | 2010-11 → 2019-20 (10) | Manchester City |
| Manchester City FC ⟶ | 2020-21 → 2025-26 (6) | Manchester City |
| Manchester United | 2010-11 → 2019-20 (10) | Manchester United |
| Manchester United FC ⟶ | 2020-21 → 2025-26 (6) | Manchester United |
| Middlesbrough FC ⟶ | 2016-17 → 2016-17 (1) | Middlesbrough |
| Newcastle United | 2010-11 → 2019-20 (9) | Newcastle United |
| Newcastle United FC ⟶ | 2020-21 → 2025-26 (6) | Newcastle United |
| Norwich City | 2011-12 → 2019-20 (5) | Norwich City |
| Norwich City FC ⟶ | 2021-22 → 2021-22 (1) | Norwich City |
| Nottingham Forest FC ⟶ | 2022-23 → 2025-26 (4) | Nottingham Forest |
| Queens Park Rangers | 2011-12 → 2014-15 (3) | Queens Park Rangers |
| Reading FC ⟶ | 2012-13 → 2012-13 (1) | Reading |
| Sheffield United | 2019-20 → 2019-20 (1) | Sheffield United |
| Sheffield United FC ⟶ | 2020-21 → 2023-24 (2) | Sheffield United |
| Southampton FC ⟶ | 2012-13 → 2024-25 (12) | Southampton |
| Stoke City | 2010-11 → 2017-18 (8) | Stoke City |
| Sunderland AFC ⟶ | 2010-11 → 2025-26 (8) | Sunderland |
| Swansea City | 2011-12 → 2017-18 (7) | Swansea City |
| Tottenham Hotspur | 2010-11 → 2019-20 (10) | Tottenham Hotspur |
| Tottenham Hotspur FC ⟶ | 2020-21 → 2025-26 (6) | Tottenham Hotspur |
| Watford FC ⟶ | 2015-16 → 2021-22 (6) | Watford |
| West Bromwich Albion | 2010-11 → 2017-18 (8) | West Bromwich Albion |
| West Bromwich Albion FC ⟶ | 2020-21 → 2020-21 (1) | West Bromwich Albion |
| West Ham United | 2010-11 → 2019-20 (9) | West Ham United |
| West Ham United FC ⟶ | 2020-21 → 2025-26 (6) | West Ham United |
| Wigan Athletic | 2010-11 → 2012-13 (3) | Wigan Athletic |
| Wolverhampton Wanderers | 2010-11 → 2019-20 (4) | Wolverhampton Wanderers |
| Wolverhampton Wanderers FC ⟶ | 2020-21 → 2025-26 (6) | Wolverhampton Wanderers |

## La Liga (`es.1`)

- raw names: 42 | canonical clubs: 33 (adjudicated: 33)
- multi-variant normalization clusters: 3

| Raw name | Seasons | Canonical |
|---|---|---|
| Athletic Club | 2012-13 → 2025-26 (14) | Athletic Club |
| Atlético Madrid | 2012-13 → 2019-20 (8) | Atlético Madrid |
| CA Osasuna ⟶ | 2012-13 → 2025-26 (10) | Osasuna |
| CD Alavés ⟶ | 2016-17 → 2019-20 (4) | Alavés |
| CD Leganés ⟶ | 2016-17 → 2024-25 (5) | Leganés |
| Club Atlético de Madrid ⟶ | 2020-21 → 2025-26 (6) | Atlético Madrid |
| Cádiz CF ⟶ | 2020-21 → 2023-24 (4) | Cádiz |
| Córdoba CF ⟶ | 2014-15 → 2014-15 (1) | Córdoba |
| Deportivo Alavés ⟶ | 2020-21 → 2025-26 (5) | Alavés |
| Deportivo La Coruña | 2012-13 → 2017-18 (5) | Deportivo La Coruña |
| Elche CF ⟶ | 2013-14 → 2025-26 (6) | Elche |
| Espanyol Barcelona ⟶ | 2012-13 → 2019-20 (8) | Espanyol |
| FC Barcelona ⟶ | 2012-13 → 2025-26 (14) | Barcelona |
| Getafe CF ⟶ | 2012-13 → 2025-26 (13) | Getafe |
| Girona FC ⟶ | 2017-18 → 2025-26 (6) | Girona |
| Granada CF ⟶ | 2012-13 → 2023-24 (9) | Granada |
| Levante UD ⟶ | 2012-13 → 2025-26 (10) | Levante |
| Málaga CF ⟶ | 2012-13 → 2017-18 (6) | Málaga |
| RC Celta ⟶ | 2012-13 → 2019-20 (8) | Celta Vigo |
| RC Celta de Vigo ⟶ | 2020-21 → 2025-26 (6) | Celta Vigo |
| RCD Espanyol de Barcelona ⟶ | 2021-22 → 2025-26 (4) | Espanyol |
| RCD Mallorca ⟶ | 2012-13 → 2025-26 (7) | Mallorca |
| Rayo Vallecano | 2012-13 → 2018-19 (5) | Rayo Vallecano |
| Rayo Vallecano de Madrid ⟶ | 2021-22 → 2025-26 (5) | Rayo Vallecano |
| Real Betis | 2012-13 → 2019-20 (7) | Real Betis |
| Real Betis Balompié ⟶ | 2020-21 → 2025-26 (6) | Real Betis |
| Real Madrid | 2012-13 → 2019-20 (8) | Real Madrid |
| Real Madrid CF ⟶ | 2020-21 → 2025-26 (6) | Real Madrid |
| Real Oviedo | 2025-26 → 2025-26 (1) | Real Oviedo |
| Real Sociedad | 2012-13 → 2019-20 (8) | Real Sociedad |
| Real Sociedad de Fútbol ⟶ | 2020-21 → 2025-26 (6) | Real Sociedad |
| Real Valladolid | 2012-13 → 2019-20 (4) | Real Valladolid |
| Real Valladolid CF ⟶ | 2020-21 → 2024-25 (3) | Real Valladolid |
| Real Zaragoza | 2012-13 → 2012-13 (1) | Real Zaragoza |
| SD Eibar ⟶ | 2014-15 → 2020-21 (7) | Eibar |
| SD Huesca ⟶ | 2018-19 → 2020-21 (2) | Huesca |
| Sevilla FC ⟶ | 2012-13 → 2025-26 (14) | Sevilla |
| Sporting Gijón | 2015-16 → 2016-17 (2) | Sporting Gijón |
| UD Almería ⟶ | 2013-14 → 2023-24 (4) | Almería |
| UD Las Palmas ⟶ | 2015-16 → 2024-25 (5) | Las Palmas |
| Valencia CF ⟶ | 2012-13 → 2025-26 (14) | Valencia |
| Villarreal CF ⟶ | 2013-14 → 2025-26 (13) | Villarreal |

## Bundesliga (`de.1`)

- raw names: 39 | canonical clubs: 32 (adjudicated: 32)
- multi-variant normalization clusters: 6

| Raw name | Seasons | Canonical |
|---|---|---|
| 1. FC Heidenheim 1846 ⟶ | 2023-24 → 2025-26 (3) | Heidenheim |
| 1. FC Kaiserslautern ⟶ | 2010-11 → 2011-12 (2) | Kaiserslautern |
| 1. FC Köln ⟶ | 2010-11 → 2025-26 (12) | Köln |
| 1. FC Nürnberg ⟶ | 2010-11 → 2018-19 (5) | Nürnberg |
| 1. FC Union Berlin ⟶ | 2019-20 → 2025-26 (7) | Union Berlin |
| 1. FSV Mainz 05 ⟶ | 2010-11 → 2025-26 (16) | Mainz |
| 1899 Hoffenheim ⟶ | 2010-11 → 2019-20 (10) | Hoffenheim |
| Arminia Bielefeld | 2020-21 → 2021-22 (2) | Arminia Bielefeld |
| Bayer 04 Leverkusen ⟶ | 2020-21 → 2025-26 (6) | Bayer Leverkusen |
| Bayer Leverkusen | 2010-11 → 2019-20 (10) | Bayer Leverkusen |
| Bayern München | 2010-11 → 2019-20 (10) | Bayern München |
| Bor. Mönchengladbach ⟶ | 2010-11 → 2019-20 (10) | Borussia Mönchengladbach |
| Borussia Dortmund | 2010-11 → 2025-26 (16) | Borussia Dortmund |
| Borussia Mönchengladbach | 2020-21 → 2025-26 (6) | Borussia Mönchengladbach |
| Eintracht Braunschweig | 2013-14 → 2013-14 (1) | Eintracht Braunschweig |
| Eintracht Frankfurt | 2010-11 → 2025-26 (15) | Eintracht Frankfurt |
| FC Augsburg ⟶ | 2011-12 → 2025-26 (15) | Augsburg |
| FC Bayern München ⟶ | 2020-21 → 2025-26 (6) | Bayern München |
| FC Ingolstadt 04 ⟶ | 2015-16 → 2016-17 (2) | Ingolstadt |
| FC Schalke 04 ⟶ | 2010-11 → 2022-23 (12) | Schalke |
| FC St. Pauli ⟶ | 2010-11 → 2010-11 (1) | St. Pauli |
| FC St. Pauli 1910 ⟶ | 2024-25 → 2025-26 (2) | St. Pauli |
| Fortuna Düsseldorf | 2012-13 → 2019-20 (3) | Fortuna Düsseldorf |
| Hamburger SV | 2010-11 → 2025-26 (9) | Hamburger SV |
| Hannover 96 ⟶ | 2010-11 → 2018-19 (8) | Hannover |
| Hertha BSC | 2011-12 → 2022-23 (11) | Hertha BSC |
| Holstein Kiel | 2024-25 → 2024-25 (1) | Holstein Kiel |
| RB Leipzig | 2016-17 → 2025-26 (10) | RB Leipzig |
| SC Freiburg ⟶ | 2010-11 → 2025-26 (15) | Freiburg |
| SC Paderborn 07 ⟶ | 2014-15 → 2019-20 (2) | Paderborn |
| SV Darmstadt 98 ⟶ | 2015-16 → 2023-24 (3) | Darmstadt |
| SV Werder Bremen ⟶ | 2020-21 → 2025-26 (5) | Werder Bremen |
| SpVgg Greuther Fürth ⟶ | 2012-13 → 2012-13 (1) | Greuther Fürth |
| SpVgg Greuther Fürth 1903 ⟶ | 2021-22 → 2021-22 (1) | Greuther Fürth |
| TSG 1899 Hoffenheim ⟶ | 2020-21 → 2025-26 (6) | Hoffenheim |
| VfB Stuttgart ⟶ | 2010-11 → 2025-26 (14) | Stuttgart |
| VfL Bochum 1848 ⟶ | 2021-22 → 2024-25 (4) | Bochum |
| VfL Wolfsburg ⟶ | 2010-11 → 2025-26 (16) | Wolfsburg |
| Werder Bremen | 2010-11 → 2019-20 (10) | Werder Bremen |

## Serie A (`it.1`)

- raw names: 47 | canonical clubs: 38 (adjudicated: 38)
- multi-variant normalization clusters: 7

| Raw name | Seasons | Canonical |
|---|---|---|
| AC Cesena ⟶ | 2014-15 → 2014-15 (1) | Cesena |
| AC Milan ⟶ | 2013-14 → 2025-26 (13) | Milan |
| AC Monza ⟶ | 2022-23 → 2024-25 (3) | Monza |
| AC Pisa 1909 ⟶ | 2025-26 → 2025-26 (1) | Pisa |
| ACF Fiorentina ⟶ | 2013-14 → 2025-26 (13) | Fiorentina |
| AS Livorno ⟶ | 2013-14 → 2013-14 (1) | Livorno |
| AS Roma ⟶ | 2013-14 → 2025-26 (13) | Roma |
| Atalanta | 2013-14 → 2019-20 (7) | Atalanta |
| Atalanta BC ⟶ | 2020-21 → 2025-26 (6) | Atalanta |
| Benevento Calcio ⟶ | 2017-18 → 2020-21 (2) | Benevento |
| Bologna FC ⟶ | 2013-14 → 2019-20 (6) | Bologna |
| Bologna FC 1909 ⟶ | 2020-21 → 2025-26 (6) | Bologna |
| Brescia Calcio ⟶ | 2019-20 → 2019-20 (1) | Brescia |
| Cagliari Calcio ⟶ | 2013-14 → 2025-26 (11) | Cagliari |
| Calcio Catania ⟶ | 2013-14 → 2013-14 (1) | Catania |
| Carpi FC ⟶ | 2015-16 → 2015-16 (1) | Carpi |
| Chievo Verona | 2013-14 → 2018-19 (6) | Chievo Verona |
| Como 1907 ⟶ | 2024-25 → 2025-26 (2) | Como |
| Delfino Pescara | 2016-17 → 2016-17 (1) | Delfino Pescara |
| Empoli FC ⟶ | 2014-15 → 2024-25 (8) | Empoli |
| FC Crotone ⟶ | 2016-17 → 2020-21 (3) | Crotone |
| FC Internazionale Milano ⟶ | 2020-21 → 2025-26 (6) | Inter |
| Frosinone Calcio ⟶ | 2015-16 → 2023-24 (3) | Frosinone |
| Genoa CFC ⟶ | 2013-14 → 2025-26 (12) | Genoa |
| Hellas Verona | 2013-14 → 2019-20 (5) | Hellas Verona |
| Hellas Verona FC ⟶ | 2020-21 → 2025-26 (6) | Hellas Verona |
| Inter | 2013-14 → 2019-20 (7) | Inter |
| Juventus | 2013-14 → 2019-20 (7) | Juventus |
| Juventus FC ⟶ | 2020-21 → 2025-26 (6) | Juventus |
| Lazio Roma ⟶ | 2013-14 → 2019-20 (7) | Lazio |
| Parma Calcio 1913 ⟶ | 2018-19 → 2025-26 (5) | Parma |
| Parma FC ⟶ | 2013-14 → 2014-15 (2) | Parma |
| SPAL 2013 Ferrara ⟶ | 2017-18 → 2019-20 (3) | SPAL |
| SS Lazio ⟶ | 2020-21 → 2025-26 (6) | Lazio |
| SSC Napoli ⟶ | 2013-14 → 2025-26 (13) | Napoli |
| Sampdoria | 2013-14 → 2019-20 (7) | Sampdoria |
| Sassuolo Calcio ⟶ | 2013-14 → 2019-20 (7) | Sassuolo |
| Spezia Calcio ⟶ | 2020-21 → 2022-23 (3) | Spezia |
| Torino FC ⟶ | 2013-14 → 2025-26 (13) | Torino |
| UC Sampdoria ⟶ | 2020-21 → 2022-23 (3) | Sampdoria |
| US Cremonese ⟶ | 2022-23 → 2025-26 (2) | Cremonese |
| US Lecce ⟶ | 2019-20 → 2025-26 (5) | Lecce |
| US Palermo ⟶ | 2014-15 → 2016-17 (3) | Palermo |
| US Salernitana 1919 ⟶ | 2021-22 → 2023-24 (3) | Salernitana |
| US Sassuolo Calcio ⟶ | 2020-21 → 2025-26 (5) | Sassuolo |
| Udinese Calcio ⟶ | 2013-14 → 2025-26 (13) | Udinese |
| Venezia FC ⟶ | 2021-22 → 2024-25 (2) | Venezia |

## Ligue 1 (`fr.1`)

- raw names: 40 | canonical clubs: 34 (adjudicated: 34)
- multi-variant normalization clusters: 3

| Raw name | Seasons | Canonical |
|---|---|---|
| AC Ajaccio ⟶ | 2022-23 → 2022-23 (1) | Ajaccio |
| AJ Auxerre ⟶ | 2022-23 → 2025-26 (3) | Auxerre |
| AS Monaco ⟶ | 2014-15 → 2022-23 (9) | Monaco |
| AS Monaco FC ⟶ | 2023-24 → 2025-26 (3) | Monaco |
| AS Nancy Lorraine ⟶ | 2016-17 → 2016-17 (1) | Nancy Lorraine |
| AS Saint-Étienne ⟶ | 2014-15 → 2024-25 (9) | Saint-Étienne |
| Amiens SC ⟶ | 2017-18 → 2019-20 (3) | Amiens |
| Angers SCO ⟶ | 2015-16 → 2025-26 (10) | Angers |
| Clermont Foot 63 ⟶ | 2021-22 → 2023-24 (3) | Clermont Foot |
| Dijon FCO ⟶ | 2016-17 → 2020-21 (5) | Dijon |
| EA Guingamp ⟶ | 2014-15 → 2018-19 (5) | Guingamp |
| ESTAC Troyes ⟶ | 2015-16 → 2022-23 (4) | Troyes |
| FC Lorient ⟶ | 2014-15 → 2025-26 (8) | Lorient |
| FC Metz ⟶ | 2014-15 → 2025-26 (8) | Metz |
| FC Nantes ⟶ | 2014-15 → 2025-26 (12) | Nantes |
| Gazélec FC Ajaccio ⟶ | 2015-16 → 2015-16 (1) | Gazélec Ajaccio |
| Girondins Bordeaux ⟶ | 2014-15 → 2021-22 (8) | Bordeaux |
| Le Havre AC ⟶ | 2023-24 → 2025-26 (3) | Le Havre |
| Lille OSC ⟶ | 2014-15 → 2025-26 (12) | Lille |
| Montpellier HSC ⟶ | 2014-15 → 2024-25 (11) | Montpellier |
| Nîmes Olympique ⟶ | 2018-19 → 2020-21 (3) | Nîmes |
| OGC Nice ⟶ | 2014-15 → 2025-26 (12) | Nice |
| Olympique Lyonnais ⟶ | 2014-15 → 2025-26 (12) | Lyon |
| Olympique Marseille ⟶ | 2014-15 → 2022-23 (9) | Marseille |
| Olympique de Marseille ⟶ | 2023-24 → 2025-26 (3) | Marseille |
| Paris FC ⟶ | 2025-26 → 2025-26 (1) | Paris |
| Paris Saint-Germain | 2014-15 → 2022-23 (9) | Paris Saint-Germain |
| Paris Saint-Germain FC ⟶ | 2023-24 → 2025-26 (3) | Paris Saint-Germain |
| RC Lens ⟶ | 2014-15 → 2022-23 (4) | Lens |
| RC Strasbourg ⟶ | 2017-18 → 2022-23 (6) | Strasbourg |
| RC Strasbourg Alsace ⟶ | 2023-24 → 2025-26 (3) | Strasbourg |
| Racing Club de Lens ⟶ | 2023-24 → 2025-26 (3) | Lens |
| SC Bastia ⟶ | 2014-15 → 2016-17 (3) | Bastia |
| SM Caen ⟶ | 2014-15 → 2018-19 (5) | Caen |
| Stade Brestois 29 ⟶ | 2019-20 → 2025-26 (7) | Stade Brestois |
| Stade Rennais | 2014-15 → 2022-23 (9) | Stade Rennais |
| Stade Rennais FC 1901 ⟶ | 2023-24 → 2025-26 (3) | Stade Rennais |
| Stade de Reims | 2014-15 → 2024-25 (9) | Stade de Reims |
| Toulouse FC ⟶ | 2014-15 → 2025-26 (10) | Toulouse |
| Évian Thonon Gaillard | 2014-15 → 2014-15 (1) | Évian Thonon Gaillard |
