import { useEffect, useState } from "react";

// Relative paths only: works on localhost, in Docker, and in Azure unchanged.
async function getJson(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`${path} returned ${res.status}`);
  return res.json();
}

export default function App() {
  const [info, setInfo] = useState(null);
  const [projects, setProjects] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([getJson("/api/info"), getJson("/api/projects")])
      .then(([i, p]) => {
        setInfo(i);
        setProjects(p);
      })
      .catch((e) => setError(e.message));
  }, []);

  return (
    <main className="page">
      <header>
        <h1>Allocator</h1>
        <p className="sub">Deployment test build</p>
      </header>

      {error && <p className="error">Backend not reachable: {error}</p>}

      {info && (
        <section className="status">
          <div><span>Environment</span><strong>{info.environment}</strong></div>
          <div><span>Version</span><strong>{info.version}</strong></div>
          <div><span>Secret configured</span><strong>{info.secret_configured ? "Yes" : "No"}</strong></div>
          <div><span>Served by</span><strong>{info.hostname}</strong></div>
        </section>
      )}

      <section>
        <h2>Projects</h2>
        <table>
          <thead>
            <tr><th>Project</th><th>Owner</th><th>Allocated hours</th></tr>
          </thead>
          <tbody>
            {projects.map((p) => (
              <tr key={p.id}>
                <td>{p.name}</td><td>{p.owner}</td><td>{p.hours}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </main>
  );
}
