# med_rag_frontend

> Frontend for a Generative AI-based Medical Knowledge Retrieval and Q&A System, Following Modern Web Development Best Practices

## Features

- 🚀 [Vue 3](https://vuejs.org/) with Composition API and `<script setup>`
- 🔧 [TypeScript](https://www.typescriptlang.org/) for type safety
- ⚡️ [Vite](https://vitejs.dev/) for fast development and optimized builds
- 📦 [Pinia](https://pinia.vuejs.org/) for state management
- 🔄 [Vue Router](https://router.vuejs.org/) for client-side routing
- 🧪 Testing setup with [Vitest](https://vitest.dev/)
- 🎨 CSS preprocessing with SCSS
- 📱 Responsive design utilities
- 🔒 Authentication flow implementation
- 🧩 Component architecture best practices

## Getting Started

### Prerequisites

- Bun

### Installation

```bash
cd frontend

# Install dependencies
bun install

# Start development server
bun run dev
```

### Build for Production

```bash
bun run build
```

## Project Structure

```
├── public/              # Static assets
├── src/
│   ├── api/            # API service layer
│   ├── assets/         # Assets that will be processed by the build
│   ├── components/     # Reusable Vue components
│   ├── layouts/        # Layout components
│   ├── plugins/        # Vue plugins and extensions
│   ├── router/         # Vue Router configuration
│   ├── stores/         # Pinia stores
│   ├── types/          # TypeScript type definitions
│   ├── utils/          # Utility functions
│   ├── pages/          # Page components
│   ├── App.vue         # Root component
│   └── main.ts         # Application entry point
├── eslint.config.ts    # ESLint configuration
├── .gitignore          # Git ignore rules
├── index.html          # HTML entry point
├── package.json        # Project dependencies and scripts
├── tsconfig.json       # TypeScript configuration
├── vite.config.ts      # Vite configuration
├── bun.lockb           # Bun lock file
└── README.md           # Project documentation
```

## Documentation

For detailed documentation on Vue 3, check out the [Vue.js Documentation](https://vuejs.org/guide/introduction.html).

For TypeScript in Vue, refer to the [Vue TypeScript Guide](https://vuejs.org/guide/typescript/overview.html).
