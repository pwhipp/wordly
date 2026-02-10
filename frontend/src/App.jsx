import AdminPanel from "./components/AdminPanel";
import GameApp from "./components/GameApp";

export default function App() {
  return window.location.pathname === "/admin" ? <AdminPanel /> : <GameApp />;
}
