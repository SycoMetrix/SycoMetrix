# Tech Stack

SycoMetrix is a working frontend dashboard backed by a database. This page lists the tools used at each layer of the project.

## Overview

| Layer                         | Technology                 |
|-------------------------------|----------------------------|
| Backend                       | Python, Flask              |
| Database                      | PostgreSQL                 |
| Frontend dashboard            | HTML, CSS, JavaScript      |
| Data analysis & visualization | Plotly.js, Pandas, NumPy   |
| LLM interaction               | Python SDKs, HTTP requests |
| Version control               | GitHub                     |
| Project management            | Trello                     |
| Testing                       | pytest                     |

## Backend

**Python** and **Flask** make up the backend layer, serving the dashboard and handling requests between the frontend, database, and LLMs.

## Database

**PostgreSQL** stores experiments and their results. Its relational structure fits experiment result tracking, where test cases, prompt variations, responses, and assessments are linked to one another. See [Database design](database_er_diagrams.md).

## Frontend Dashboard

The dashboard is built with plain **HTML**, **CSS**, and **JavaScript**.

## Data Analysis and Visualization

- **Pandas** and **NumPy** for processing and analyzing experiment results.
- **Plotly.js** for charts in the dashboard.

## LLM Interaction

LLMs are called through their **Python SDKs** and direct **HTTP requests** to collect responses. See [LLM API usage](API.md).

## Version Control

Source code is hosted on **GitHub**.

## Project Management

Tasks and progress are tracked on **Trello** boards.

## Testing

**pytest** is used for testing to keep the codebase healthy as the project iterates.

## Related Docs

- [Project overview](overview.md)
- [Database design](database_er_diagrams.md)
- [LLM API usage](API.md)
