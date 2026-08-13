FROM node:20-alpine

WORKDIR /app

COPY backend ./backend
COPY frontend ./frontend
COPY data ./data

WORKDIR /app/backend

RUN npm install --omit=dev

EXPOSE 3000

CMD ["node", "server.js"]
