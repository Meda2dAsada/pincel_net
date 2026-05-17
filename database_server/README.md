# database_server

Servidor UDP que recibe peticiones cifradas y las persiste en MySQL/MariaDB usando SQLAlchemy.

## Requisitos

- Python 3.10+
- MariaDB corriendo en `127.0.0.1:3306`
- HeidiSQL (u otro cliente MySQL)

## Primeros pasos

### 1. Levantar MariaDB

Si el servicio no está corriendo, abre PowerShell como administrador:

```powershell
net start MariaDB
```

### 2. Crear la base de datos

Conéctate en HeidiSQL y ejecuta:

```sql
CREATE DATABASE IF NOT EXISTS guessing_game CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 3. Instalar dependencias

```powershell
pip install -r requirements.txt
```

### 4. Inicializar Alembic

Solo la primera vez:

```powershell
alembic init migrations
```

Reemplaza el `migrations/env.py` generado con el del repositorio.

Luego crea el template de migraciones con el encoding correcto:

```powershell
Remove-Item "migrations\script.py.mako"

$content = @'
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
'@

[System.IO.File]::WriteAllText("$PWD\migrations\script.py.mako", $content, [System.Text.Encoding]::UTF8)
```

### 5. Generar y aplicar migraciones

```powershell
alembic revision --autogenerate -m "create users rooms guesses"
alembic upgrade head
```

Esto crea las tablas `users`, `rooms` y `guesses` en HeidiSQL.

### 6. Levantar el servidor

```powershell
python db_server.py
```

## Estructura

```
database_server/
├── db_server.py        # servidor UDP principal
├── database.py         # configuracion de SQLAlchemy
├── models/
│   ├── user.py
│   ├── room.py
│   └── guess.py
├── migrations/
│   └── env.py
├── alembic.ini
└── requirements.txt
```