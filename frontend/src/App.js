import "@/index.css";
import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Toaster } from "sonner";
import HomePage from "@/pages/Home";

function App() {
  return (
    <BrowserRouter>
      <Toaster
        position="bottom-center"
        theme="light"
        toastOptions={{
          style: {
            background: "#ffffff",
            border: "1px solid rgba(26,34,28,0.16)",
            color: "#1a221c",
            fontFamily: "'Manrope', sans-serif",
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
