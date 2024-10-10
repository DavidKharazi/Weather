from fastapi import FastAPI, Depends, Query, HTTPException
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, Column, Integer, String, DateTime, desc, asc
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel

# Настройка базы данных: подключение к базе SQLite и настройка сессии
DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Модель таблицы логов в базе данных
class Log(Base):
    __tablename__ = "logs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer)
    command = Column(String)
    response = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)

# Создание таблицы в базе данных, если ее еще нет
Base.metadata.create_all(bind=engine)

# Инициализация FastAPI приложения
app = FastAPI()

# Подключение статических файлов (например, для отображения статичных ресурсов)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Зависимость для получения сессии базы данных
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Модель ответа для одного лога
class LogResponse(BaseModel):
    id: int
    user_id: int
    command: str
    response: str
    timestamp: datetime

# Модель ответа для пагинации логов
class LogsResponse(BaseModel):
    logs: List[LogResponse]
    total_pages: int
    current_page: int
    next_page: Optional[int]
    prev_page: Optional[int]

# Эндпоинт для получения списка логов с фильтрами (по дате, пользователю, сортировке и пагинации)
@app.get("/logs", response_model=LogsResponse)
async def get_logs(
    user_id: Optional[str] = Query(None, alias="user_id"),
    page: int = Query(1, alias="page", ge=1),
    per_page: int = Query(10, alias="per_page", ge=1, le=100),
    order: str = Query("desc", alias="order", pattern="^(asc|desc)$"),
    start_date: Optional[str] = Query(None, alias="start_date"),
    end_date: Optional[str] = Query(None, alias="end_date"),
    db: Session = Depends(get_db)
):
    # Создание запроса к базе данных для выборки логов
    query = db.query(Log)

    # Фильтрация по user_id, если указано
    if user_id and user_id != "all":
        try:
            user_id_int = int(user_id)
            query = query.filter(Log.user_id == user_id_int)
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid user ID")

    # Фильтрация по начальной дате, если указано
    if start_date:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        query = query.filter(Log.timestamp >= start_dt)

    # Фильтрация по конечной дате, если указано
    if end_date:
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        query = query.filter(Log.timestamp <= end_dt)

    # Сортировка по времени
    if order == "asc":
        query = query.order_by(asc(Log.timestamp))
    else:
        query = query.order_by(desc(Log.timestamp))

    # Пагинация: подсчет общего количества логов и получение соответствующей страницы
    total_logs = query.count()
    logs = query.offset((page - 1) * per_page).limit(per_page).all()

    # Подсчет количества страниц
    total_pages = (total_logs + per_page - 1) // per_page
    next_page = page + 1 if page < total_pages else None
    prev_page = page - 1 if page > 1 else None

    # Возврат ответа с логами и информацией о пагинации
    return LogsResponse(
        logs=[LogResponse(
            id=log.id,
            user_id=log.user_id,
            command=log.command,
            response=log.response,
            timestamp=log.timestamp
        ) for log in logs],
        total_pages=total_pages,
        current_page=page,
        next_page=next_page,
        prev_page=prev_page
    )

# Эндпоинт для получения логов конкретного пользователя (с фильтрацией по дате и пагинацией)
@app.get("/logs/{user_id}", response_model=LogsResponse)
async def get_logs_by_user(
    user_id: int,
    page: int = Query(1, alias="page", ge=1),
    per_page: int = Query(10, alias="per_page", ge=1, le=100),
    order: str = Query("desc", alias="order", pattern="^(asc|desc)$"),
    start_date: Optional[str] = Query(None, alias="start_date"),
    end_date: Optional[str] = Query(None, alias="end_date"),
    db: Session = Depends(get_db)
):
    # Создание запроса для получения логов по user_id
    query = db.query(Log).filter(Log.user_id == user_id)

    # Фильтрация по начальной и конечной дате
    if start_date:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        query = query.filter(Log.timestamp >= start_dt)
    if end_date:
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        query = query.filter(Log.timestamp <= end_dt)

    # Сортировка по времени
    if order == "asc":
        query = query.order_by(asc(Log.timestamp))
    else:
        query = query.order_by(desc(Log.timestamp))

    # Пагинация: подсчет общего количества логов и получение соответствующей страницы
    total_logs = query.count()
    logs = query.offset((page - 1) * per_page).limit(per_page).all()

    # Подсчет количества страниц и подготовка ответа
    total_pages = (total_logs + per_page - 1) // per_page
    next_page = page + 1 if page < total_pages else None
    prev_page = page - 1 if page > 1 else None

    # Возврат ответа с логами и информацией о пагинации для конкретного пользователя
    return LogsResponse(
        logs=[LogResponse(
            id=log.id,
            user_id=log.user_id,
            command=log.command,
            response=log.response,
            timestamp=log.timestamp
        ) for log in logs],
        total_pages=total_pages,
        current_page=page,
        next_page=next_page,
        prev_page=prev_page
    )

# Запуск приложения через Uvicorn
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
