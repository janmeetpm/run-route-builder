import "@/index.css";
import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Toaster } from "sonner";
import HomePage from "@/pages/Home";

function App() {
  return (
    <BrowserRouter>
      <Toaster
        position="top-center"
        theme="dark"
        toastOptions={{
          style: {
            background: "#121212",
            border: "1px solid rgba(255,255,255,0.12)",
            color: "#fff",
            fontFamily: "'DM Sans', sans-serif",
          },
        }}
      />
      <Routes>
        <Route path="/" element={<HomePage />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
