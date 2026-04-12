# Smart CRM and Lead Management Platform

## Project Description

Manage client leads and sales follow-up process.

## What to Build

- Lead tracking dashboard
- Client communication logs
- Follow-up reminders

## Backend

- Django / Firebase

## Current Stack (Implemented)

- Backend: Django + SQLite
- Frontend: React + Vite

## Project Structure

- frontend: React app (landing page, login page, CRM workspace UI)
- backend: Django API (auth, leads, dashboard metrics)

## Run Locally

1. Backend setup:
- cd backend
- python -m venv .venv
- source .venv/bin/activate
- pip install -r requirements.txt
- python manage.py migrate
- python manage.py createsuperuser
- python manage.py runserver

2. Frontend setup:
- cd frontend
- npm install
- npm run dev

3. API URL (optional):
- frontend uses VITE_API_URL
- default value: http://127.0.0.1:8000/api

## API Endpoints

- POST /api/auth/login/
- POST /api/auth/logout/
- GET /api/auth/session/
- GET /api/dashboard/
- GET /api/leads/
- POST /api/leads/
- PATCH /api/leads/<lead_id>/
- POST /api/leads/<lead_id>/notes/

## How to Handle Leads Data

Use two interfaces instead of one overloaded screen:

1. Lead Intake Interface
- Purpose: capture clean lead input quickly
- Fields: company, contact, source, owner, estimated value, notes
- Used by: marketing ops, SDRs, admin

2. Sales Workspace Interface
- Purpose: manage lead progression and follow-up
- Includes: pipeline cards, lead table, reminders, activity timeline
- Used by: account execs, sales managers

Recommended flow:
- new lead enters through intake form
- lead appears in workspace as stage=new
- sales team updates stage over time (qualified -> proposal -> negotiation -> won/lost)

## Expected Output

- Lead pipeline
- Conversion reports
