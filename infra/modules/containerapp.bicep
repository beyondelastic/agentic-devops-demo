param name string
@description('azd service tag name (api / tools / frontend).')
param serviceName string
param location string
param tags object
param environmentId string
param identityId string
param acrLoginServer string
param targetPort int
param externalIngress bool
param appInsightsConnectionString string
param extraEnv array
param minReplicas int = 1
param maxReplicas int = 5
param concurrentRequests int = 30
@description('Whether this container app already exists. When true, reuse the deployed image and enable probes; when false, use a placeholder so first-time provision succeeds before azd deploy pushes the real image.')
param exists bool = false
@description('Pre-resolved image reference. On first provision pass the placeholder; on subsequent provisions pass the existing image so azd deploy can update it. Lookup is done in the parent to avoid a self-referential circular dependency inside this module.')
param image string

var probes = exists ? [
  {
    type: 'Liveness'
    httpGet: { path: '/healthz', port: targetPort }
    initialDelaySeconds: 5
    periodSeconds: 30
  }
  {
    type: 'Readiness'
    httpGet: { path: serviceName == 'frontend' ? '/healthz' : '/readyz', port: targetPort }
    initialDelaySeconds: 3
    periodSeconds: 10
  }
] : []

var combinedTags = union(tags, {
  'azd-service-name': serviceName
})

resource app 'Microsoft.App/containerApps@2024-03-01' = {
  name: name
  location: location
  tags: combinedTags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identityId}': {}
    }
  }
  properties: {
    managedEnvironmentId: environmentId
    workloadProfileName: 'Consumption'
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: externalIngress
        targetPort: targetPort
        transport: 'auto'
        allowInsecure: false
      }
      registries: [
        {
          server: acrLoginServer
          identity: identityId
        }
      ]
    }
    template: {
      containers: [
        {
          name: serviceName
          image: image
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: union(
            [
              { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsightsConnectionString }
              { name: 'PORT', value: string(targetPort) }
            ],
            extraEnv
          )
          probes: probes
        }
      ]
      scale: {
        minReplicas: minReplicas
        maxReplicas: maxReplicas
        rules: [
          {
            name: 'http-concurrency'
            http: {
              metadata: {
                concurrentRequests: string(concurrentRequests)
              }
            }
          }
        ]
      }
    }
  }
}

output id string = app.id
output name string = app.name
output fqdn string = app.properties.configuration.ingress.fqdn
