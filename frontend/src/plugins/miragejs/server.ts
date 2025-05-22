import { createServer, Model } from 'miragejs'
import { ulid } from 'ulid'
import setupRoutes from './routes'

export const startMockServer = () =>
  createServer({
    environment: 'development',
    models: {
      user: Model,
    },

    seeds(server) {
      server.create('user', {
        id: ulid(),
        name: 'DNT',
        email: 'admin@gmail.com',
        password: '123',
        token: 'faketoken',
      })
    },

    routes() {
      this.namespace = 'api'

      setupRoutes(this)

      this.passthrough()
    },
  })
