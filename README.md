# AoE4 Stats

Panel web Django para consultar perfiles y estadísticas de civilizaciones a partir de la API pública de AoE4 World.

## Requisitos

- Docker y Docker Compose, o Python 3.10+ para ejecución local.
- IDs de perfil de AoE4 World para iniciar la sincronización.

## Inicio con Docker

1. Copia `.env.example` a `.env` y define una clave aleatoria en `DJANGO_SECRET_KEY`, además de cambiar `DB_PASSWORD` y `MYSQL_ROOT_PASSWORD`.
   Si vas a entrar desde otro equipo de la red local, agrega la IP o el nombre de la VM a `DJANGO_ALLOWED_HOSTS`.
2. (Opcional) Completa `AOE4_PROFILE_IDS` con IDs separados por coma.
3. Inicia la aplicación:

   ```sh
   docker compose up --build
   ```

4. Abre `http://localhost:8000`.
5. Sincroniza perfiles y sus partidas recientes:

   ```sh
   docker compose exec web python manage.py fetch_aoe_data
   ```

   O indica IDs al ejecutar el comando:

   ```sh
   docker compose exec web python manage.py fetch_aoe_data --profile-ids 12345,67890
   ```

El comando obtiene una página (hasta 50 partidas) por perfil para cada ejecución. Puedes aumentar el límite con `--max-pages N` o consultar toda la paginación con `--max-pages 0`. Para limitar las partidas a un modo, añade `--leaderboard rm_solo`.

## Ejecución local

```sh
python -m venv .venv
# Windows: .venv\Scripts\Activate.ps1
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Por defecto, la ejecución local usa SQLite y modo debug. Define `DB_ENGINE=mysql` y las variables `DB_*` para conectarte a MySQL.

El contenedor usa Gunicorn y sirve los recursos estáticos con WhiteNoise. `runserver` queda para desarrollo local; no lo expongas como servidor de producción.

## Métricas y API

- El ELO mostrado es el rating del modo indicado por `AOE4_RATING_MODE` (por defecto `rm_solo`).
- Pick rate cuenta cada participación almacenada en una partida; una misma partida aporta una selección por jugador.
- Winrate se calcula por civilización con las partidas importadas y solo aparece al alcanzar `MIN_CIV_GAMES` (por defecto, 5).
- Las estadísticas están disponibles también en `/api/stats/`.
- La sincronización es idempotente: perfiles, partidas y participaciones se actualizan por sus IDs.

AoE4 World y su API son servicios externos. La aplicación no crea partidas nuevas ni representa historial anterior a los perfiles sincronizados. Verifica los términos y límites de uso del servicio antes de desplegar sincronizaciones periódicas.

## Pruebas

```sh
python manage.py test
```
