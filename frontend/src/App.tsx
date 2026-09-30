import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import NavBar from "./NavBar";
import HomePage from "./HomePage";
import OrchestrationPage from "./OrchestrationPage";
import { useEventStream } from "./useEventStream";

export default function App() {
  const sse = useEventStream();
  return (
    <BrowserRouter>
      <NavBar connected={sse.connected} />
      <main className="mx-auto min-h-[calc(100vh-57px)] max-w-[1600px]">
        <Routes>
          <Route path="/" element={<HomePage sse={sse} />} />
          <Route path="/orchestration" element={<OrchestrationPage sse={sse} />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </BrowserRouter>
  );
}
