## Introduction
This is just simple chatbot without any extra functionality.

## Testing
Can Test on Langgraph Studio.
Run Langgraph Studio and import studio folder

## Run local server.
Goto studio folder and open terminal
run the following command.

langgraph dev --host localhost --port 8000

## Run white UI.
Goto chat_ui folder and open a new terminal 
run the following command.
npm install
and then this one
npm run dev

go to
localhost:5173

## TO BUILD PRODUCTION DIST.
npm run build
(sometimes must run before: npm install --save-dev typescript)

## API TO SEARCH FOR NEAREST WORKSHOP.
https://api.aposto.dev.more.it/api/doc

The API call for searching workshops is /api/shops/search.
The documentation is available at api.aposto.dev.more.it, but development calls must be made to api.dev.aposto.it.