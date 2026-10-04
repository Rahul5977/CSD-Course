# CSD Course — Rahul Raj (12341680)

All lab tasks and projects for the CSD course in one repository. Each folder is self-contained
with its own README, setup steps and report. Labs that were developed as separate repositories
were merged in with their full commit history.

## Lab tasks

| Folder | Lab | What it is | Stack |
|---|---|---|---|
| [`Lab-Task/1.OpevCVAsAPI`](Lab-Task/1.OpevCVAsAPI) | Lab 2 | REST API wrapping OpenCV transforms (`/gray`, `/blur`, `/edges`, `/contours`) | Python, Flask, OpenCV |
| [`Lab-Task/2.SocketProg`](Lab-Task/2.SocketProg) | — | Raw socket client/server warm-up | Python |
| [`Lab-Task/2.ChatApp/Group-chat`](Lab-Task/2.ChatApp/Group-chat) | — | Real-time group chat over raw WebSockets *(team repo, submodule)* | Node.js, `ws` |
| [`Lab-Task/4.GroupChat-Encypted`](Lab-Task/4.GroupChat-Encypted) | Lab 4 | Group chat with end-to-end encrypted rooms *(team repo, submodule)* | Node.js, Web Crypto |
| [`Lab-Task/5.Load-Balancer`](Lab-Task/5.Load-Balancer) | Lab 5 | Load balancer over three chat backends + load generator and measurements | Node.js |
| [`Lab-Task/6.Dynamic Load Balancing and Persistent Chat`](Lab-Task/6.Dynamic%20Load%20Balancing%20and%20Persistent%20Chat) | Lab 6 | Adaptive load balancing, live backend discovery, persistent SQLite chat | Node.js, SQLite |
| [`Lab-Task/7.ProximitySearchAPI`](Lab-Task/7.ProximitySearchAPI) | Lab 7 | Proximity search API: 10 nearest locations by grid distance within a radius *(in progress)* | Python, FastAPI |

## Projects

| Folder | What it is | Stack |
|---|---|---|
| [`Project/1.PondPlanning`](Project/1.PondPlanning) | AI-based village pond planning: terrain, catchment, runoff and pond-site recommendation | Python, React |

## Cloning

Two labs are team repositories included as git submodules, so clone with:

```bash
git clone --recurse-submodules https://github.com/Rahul5977/CSD-Course.git
```
