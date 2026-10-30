# UML Design Docs

These docs describe the code as it is actually built. Each implementation ticket adds or updates a doc here in the same pull request as the code, so the diagrams never drift far from reality.

Diagrams are written in [Mermaid](https://mermaid.js.org/), which GitHub renders inline. To preview locally, use the VS Code "Markdown Preview Mermaid Support" extension or paste a diagram into the [Mermaid Live Editor](https://mermaid.live/).

## Docs

| Ticket | Doc | Diagrams |
|--------|-----|----------|
| 01 | [Project setup](01-project-setup.md) | Package, class, sequence, deployment |
| 02 | [Database models](02-database-models.md) | Package, class, sequence |
| 03 | [Prompt variations](03-prompt-variations.md) | Sequence |

The data model is documented in [Database design](../database_er_diagrams.md) (ER diagram).

## Conventions

Each doc is named after its ticket (`NN-short-name.md`) and covers what that ticket built. Include the diagrams that help explain the ticket; most will want:

| Diagram           | Mermaid type          | Use it to show                                                      |
|-------------------|-----------------------|---------------------------------------------------------------------|
| Package/component | `flowchart`           | Which modules exist and which depend on which                      |
| Class             | `classDiagram`        | Classes, their key attributes and methods, inheritance, composition |
| Sequence          | `sequenceDiagram`     | How a request or job moves through the code, step by step           |
| State             | `stateDiagram-v2`     | Lifecycles, e.g. an experiment going from draft to complete         |
| Deployment        | `flowchart`           | Processes, databases, and external services at runtime              |

Guidelines:

- **Diagram the real code.** Use the actual class, function, and module names so a reader can jump from the diagram to the file. Link the source files under each diagram.
- **Show what matters, not everything.** Leave out trivial helpers and private details unless they explain a design decision.
- **Explain decisions in prose.** A short "Design notes" section under the diagrams should say *why*, especially where the code differs from the ticket.
- **Update, don't duplicate.** If a later ticket changes something drawn in an earlier doc (e.g. ticket 05 adds a new config key), update the earlier diagram too.
