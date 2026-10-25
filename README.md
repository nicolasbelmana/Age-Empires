# Age-Empires — AoE4 Stats

![Django](https://img.shields.io/badge/Django-5.2%2B-092E20?logo=django&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![MySQL](https://img.shields.io/badge/MySQL-8.4-4479A1?logo=mysql&logoColor=white)

Panel web para explorar estadísticas de Age of Empires IV. Sincroniza perfiles y partidas desde la API pública de AoE4 World y muestra métricas de jugadores y civilizaciones.

## 📋 Tabla de contenidos

- [Características](#-características)
- [Tecnologías](#-tecnologías)
- [Instalación](#-instalación)
- [Uso](#-uso)
- [Estructura del proyecto](#-estructura-del-proyecto)
- [Contribuir](#-contribuir)
- [Licencia](#-licencia)
- [Contacto](#-contacto)

## ✨ Características

- Resumen del total de jugadores, partidas y jugador con mayor rating disponible.
- Top 10 actual de la clasificación, con puesto, rating, winrate, racha y última partida.
- Gráfico de popularidad (pick rate) por civilización.
- Gráfico de winrate por civilización, con un umbral mínimo de partidas.
- Sincronización idempotente de perfiles, partidas y participantes desde AoE4 World.
- API JSON de estadísticas en `/api/stats/`.
- Despliegue con Docker Compose, Django, Gunicorn y MySQL.

## 🛠️ Tecnologías

- [Python](https://www.python.org/) y [Django](https://www.djangoproject.com/)
- [MySQL 8.4](https://www.mysql.com/) en Docker
- [Chart.js](https://www.chartjs.org/) para los gráficos
- [AoE4 World API](https://aoe4world.com/) como fuente de datos
- Gunicorn y WhiteNoise para servir la aplicación y los recursos estáticos

## 🚀 Instalación

### Con Docker Compose

Requisitos: Git, Docker Engine y Docker Compose.

```bash
git clone https://github.com/nicolasbelmana/Age-Empires.git
cd Age-Empires
cp .env.example .env
```

Edita `.env` y configura una clave secreta y contraseñas propias. Define también `DJANGO_ALLOWED_HOSTS` con los nombres o IP desde los que accederás al panel. Por ejemplo:

```dotenv
DJANGO_SECRET_KEY=una-clave-aleatoria-larga
DJANGO_DEBUG=0
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,192.168.1.33
DB_PASSWORD=una-clave-para-la-base-de-datos
MYSQL_ROOT_PASSWORD=otra-clave-para-mysql
AOE4_PROFILE_IDS=1001
AOE4_LEADERBOARD=rm_solo
AOE4_LEADERBOARD_SIZE=10
```

No publiques el archivo `.env`; está excluido de Git.

Construye e inicia los servicios:

```bash
docker compose up -d --build
```

Abre `http://localhost:8000` desde el propio servidor o `http://IP_DEL_SERVIDOR:8000` desde un equipo que tenga acceso a la red. Si usas una VM o firewall, permite el tráfico al puerto `8000` desde la red que corresponda.

### Ejecución local sin Docker

Requisitos: Python 3.10 o superior.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

En Windows PowerShell, activa el entorno con `.venv\Scripts\Activate.ps1`. La configuración local usa SQLite por defecto; configura las variables `DB_*` y `DB_ENGINE=mysql` si quieres usar MySQL.

## 💻 Uso

### Sincronizar perfiles y partidas

Configura `AOE4_PROFILE_IDS` en `.env` con uno o varios IDs numéricos separados por coma y ejecuta:

```bash
docker compose exec web python manage.py fetch_aoe_data
```

El mismo comando actualiza también el top de la clasificación configurada en `AOE4_LEADERBOARD` (por defecto `rm_solo`). Guarda 10 jugadores por defecto; puedes cambiar el límite con `AOE4_LEADERBOARD_SIZE` (máximo 50). Para actualizar solo la clasificación sin sincronizar perfiles o partidas:

```bash
docker compose exec web python manage.py fetch_aoe_data --profile-ids ""
```

También puedes pasar los IDs directamente:

```bash
docker compose exec web python manage.py fetch_aoe_data --profile-ids 1001,2002
```

Por defecto se consulta una página (hasta 50 partidas) por perfil. Para consultar más páginas:

```bash
docker compose exec web python manage.py fetch_aoe_data --profile-ids 1001 --max-pages 3
```

Para recorrer todas las páginas disponibles, usa `--max-pages 0`. Puedes filtrar partidas por clasificación con `--leaderboard rm_solo`.

Para actualizar el código en un servidor y reconstruir el contenedor web:

```bash
git pull --ff-only origin main
docker compose up -d --build --force-recreate web
docker compose exec web python manage.py fetch_aoe_data
```

### Métricas

- El rating del jugador destacado usa el modo configurado por `AOE4_RATING_MODE` (por defecto `rm_solo`).
- El top de la clasificación viene del leaderboard actual de AoE4 World y se actualiza al ejecutar el sincronizador. Es una clasificación de temporada, no una lista de jugadores conectados en vivo.
- La marca «En vivo» indica que AoE4 World reportó el canal de Twitch del jugador como activo durante la última sincronización.
- El pick rate se calcula con las participaciones de civilizaciones almacenadas.
- El winrate se muestra cuando una civilización alcanza `MIN_CIV_GAMES` partidas (por defecto, 5).
- El endpoint JSON está disponible en `/api/stats/`.

La base de datos refleja solo los perfiles y las partidas que se hayan sincronizado. AoE4 World es un servicio externo: respeta sus términos y límites de uso.

### Pruebas

```bash
python manage.py test
```

## 📁 Estructura del proyecto

```text
Age-Empires/
├── aoe4stats/                  # Configuración y puntos de entrada de Django
├── stats/
│   ├── management/commands/    # Comando fetch_aoe_data
│   ├── migrations/             # Migraciones de la base de datos
│   ├── static/stats/           # JavaScript y estilos del panel
│   ├── templates/stats/        # Plantilla HTML del panel
│   ├── models.py               # Jugadores, partidas y participantes
│   ├── tests.py                # Pruebas
│   └── views.py                # Panel y API JSON
├── .env.example                # Plantilla de configuración
├── docker-compose.yml          # Servicios web y MySQL
├── Dockerfile
├── manage.py
└── requirements.txt
```

## 🤝 Contribuir

1. Haz un fork del repositorio.
2. Crea una rama para tu cambio: `git checkout -b feature/nueva-funcionalidad`.
3. Ejecuta las pruebas: `python manage.py test`.
4. Guarda los cambios en un commit y súbelos a tu fork.
5. Abre un Pull Request con una descripción del cambio.

## 📄 Licencia

El repositorio todavía no especifica una licencia. Hasta que se agregue una, no asumas permisos de reutilización o redistribución del código.

## 📬 Contacto

Repositorio del proyecto: [github.com/nicolasbelmana/Age-Empires](https://github.com/nicolasbelmana/Age-Empires).
