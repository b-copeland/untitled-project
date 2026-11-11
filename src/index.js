import React from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import './index.css';
import './styles/shared.css';
import { QueryClientProvider } from '@tanstack/react-query';
import {App} from './App';
import { createQueryClient } from './data/gameData';
import * as serviceWorker from './serviceWorker';

const queryClient = createQueryClient();
const container = document.getElementById('root');
document.documentElement.setAttribute('data-bs-theme', 'dark');
const root = createRoot(container); // createRoot(container!) if you use TypeScript

root.render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>
);

// If you want your app to work offline and load faster, you can change
// unregister() to register() below. Note this comes with some pitfalls.
// Learn more about service workers: https://bit.ly/CRA-PWA
serviceWorker.unregister();
