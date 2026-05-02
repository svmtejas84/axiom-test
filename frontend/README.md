# Axiom Frontend

A lightweight Next.js frontend for the Axiom credit scoring API.

## Run locally

1. Install dependencies:

```bash
cd frontend
npm install
```

2. Start the development server:

```bash
npm run dev
```

3. Open the app:

```
http://localhost:3000
```

Then visit the dashboard:

```
http://localhost:3000/dashboard
```

## Configuration

The frontend uses `NEXT_PUBLIC_API_URL` to call the backend API. By default it points to `http://localhost:8000`.

Example `.env.local`:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```
