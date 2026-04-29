targetScope = 'resourceGroup'

@minLength(3)
@maxLength(20)
@description('Short environment name (e.g. dev, demo). Used as a token in resource names.')
param environmentName string

@description('Azure region for all resources.')
param location string = resourceGroup().location

@description('Foundry/AI region (some model SKUs are region-restricted).')
param aiLocation string = location

@description('Model name to deploy in Foundry, e.g. gpt-4o-mini.')
param modelName string = 'gpt-4o-mini'

@description('Model version.')
param modelVersion string = '2024-07-18'

@description('Capacity (TPM in thousands) for the model deployment.')
param modelCapacity int = 30

@secure()
@description('Shared secret the tools service requires as the `x-api-key` header. Surfaced to the Foundry project as the `clinical_trial_matcher` connection so tool calls authenticate end-to-end.')
param toolsApiKey string = ''

var effectiveToolsApiKey = empty(toolsApiKey) ? 'demo-key' : toolsApiKey

@description('Whether the tools container app already exists (set by preprovision hook).')
param toolsExists bool = false
@description('Whether the api container app already exists (set by preprovision hook).')
param apiExists bool = false
@description('Whether the frontend container app already exists (set by preprovision hook).')
param frontendExists bool = false

@description('Tag added to all resources.')
param tags object = {
  'azd-env-name': environmentName
  workload: 'agentic-devops-demo'
}

var resourceToken = uniqueString(subscription().id, resourceGroup().id, environmentName)
var prefix = 'adgd'

var placeholderImage = 'mcr.microsoft.com/k8se/quickstart:latest'
var toolsAppName = '${prefix}-tools-${resourceToken}'
var apiAppName = '${prefix}-api-${resourceToken}'
var frontendAppName = '${prefix}-fe-${resourceToken}'

// Existing-image lookups live in the parent so the child module does not
// reference a resource with the same name as the one it deploys (which ARM
// flags as a circular dependency).
resource existingTools 'Microsoft.App/containerApps@2024-03-01' existing = if (toolsExists) {
  name: toolsAppName
}
resource existingApi 'Microsoft.App/containerApps@2024-03-01' existing = if (apiExists) {
  name: apiAppName
}
resource existingFrontend 'Microsoft.App/containerApps@2024-03-01' existing = if (frontendExists) {
  name: frontendAppName
}

var toolsImage = toolsExists ? existingTools!.properties.template.containers[0].image : placeholderImage
var apiImage = apiExists ? existingApi!.properties.template.containers[0].image : placeholderImage
var frontendImage = frontendExists ? existingFrontend!.properties.template.containers[0].image : placeholderImage

// ---------- Identity & RBAC ----------
module identity 'modules/identity.bicep' = {
  name: 'identity'
  params: {
    name: '${prefix}-mi-${resourceToken}'
    location: location
    tags: tags
  }
}

// ---------- Observability ----------
module observability 'modules/observability.bicep' = {
  name: 'observability'
  params: {
    logAnalyticsName: '${prefix}-log-${resourceToken}'
    appInsightsName: '${prefix}-appi-${resourceToken}'
    location: location
    tags: tags
  }
}

// ---------- ACR ----------
module acr 'modules/acr.bicep' = {
  name: 'acr'
  params: {
    name: replace('${prefix}acr${resourceToken}', '-', '')
    location: location
    tags: tags
    principalId: identity.outputs.principalId
  }
}

// ---------- AI Foundry ----------
module foundry 'modules/foundry.bicep' = {
  name: 'foundry'
  params: {
    accountName: '${prefix}-aifo-${resourceToken}'
    projectName: 'tm-project'
    location: aiLocation
    tags: tags
    modelName: modelName
    modelVersion: modelVersion
    modelCapacity: modelCapacity
    principalId: identity.outputs.principalId
  }
}

// ---------- Foundry project connection (OpenAPI tool auth) ----------
module foundryConnection 'modules/foundry-connection.bicep' = {
  name: 'foundry-connection'
  params: {
    accountName: foundry.outputs.accountName
    projectName: foundry.outputs.projectName
    connectionName: 'clinical_trial_matcher'
    toolsApiKey: effectiveToolsApiKey
  }
}

// ---------- Container Apps Environment ----------
module env 'modules/containerapps-env.bicep' = {
  name: 'aca-env'
  params: {
    name: '${prefix}-env-${resourceToken}'
    location: location
    tags: tags
    logAnalyticsCustomerId: observability.outputs.logAnalyticsCustomerId
    logAnalyticsSharedKey: observability.outputs.logAnalyticsSharedKey
  }
}

// ---------- Container Apps ----------
module toolsApp 'modules/containerapp.bicep' = {
  name: 'app-tools'
  params: {
    name: toolsAppName
    serviceName: 'tools'
    location: location
    tags: tags
    environmentId: env.outputs.environmentId
    identityId: identity.outputs.identityId
    acrLoginServer: acr.outputs.loginServer
    targetPort: 8000
    // External so Foundry's runtime (and the Foundry extension during agent
    // authoring) can fetch /openapi.json and call the operations.
    externalIngress: true
    appInsightsConnectionString: observability.outputs.appInsightsConnectionString
    extraEnv: [
      { name: 'TOOLS_API_KEY', value: effectiveToolsApiKey }
      // Advertised in the OpenAPI doc's `servers` so Foundry knows the base URL.
      { name: 'PUBLIC_BASE_URL', value: 'https://${prefix}-tools-${resourceToken}.${env.outputs.defaultDomain}' }
    ]
    minReplicas: 1
    maxReplicas: 5
    concurrentRequests: 30
    exists: toolsExists
    image: toolsImage
  }
}

module apiApp 'modules/containerapp.bicep' = {
  name: 'app-api'
  params: {
    name: apiAppName
    serviceName: 'api'
    location: location
    tags: tags
    environmentId: env.outputs.environmentId
    identityId: identity.outputs.identityId
    acrLoginServer: acr.outputs.loginServer
    targetPort: 8000
    externalIngress: false
    appInsightsConnectionString: observability.outputs.appInsightsConnectionString
    extraEnv: [
      { name: 'FOUNDRY_MODE', value: 'real' }
      { name: 'FOUNDRY_PROJECT_ENDPOINT', value: foundry.outputs.projectEndpoint }
      { name: 'FOUNDRY_AGENT_NAME', value: 'clinical-trial-matcher' }
      { name: 'FOUNDRY_MODEL_DEPLOYMENT_NAME', value: modelName }
      { name: 'TOOLS_SERVICE_URL', value: 'https://${toolsApp.outputs.fqdn}' }
      { name: 'TOOLS_API_KEY', value: effectiveToolsApiKey }
      { name: 'AZURE_CLIENT_ID', value: identity.outputs.clientId }
      { name: 'ENABLE_MEMORY_LEAK', value: 'false' }
    ]
    minReplicas: 1
    maxReplicas: 10
    concurrentRequests: 20
    exists: apiExists
    image: apiImage
  }
}

module frontendApp 'modules/containerapp.bicep' = {
  name: 'app-frontend'
  params: {
    name: frontendAppName
    serviceName: 'frontend'
    location: location
    tags: tags
    environmentId: env.outputs.environmentId
    identityId: identity.outputs.identityId
    acrLoginServer: acr.outputs.loginServer
    targetPort: 8080
    externalIngress: true
    appInsightsConnectionString: observability.outputs.appInsightsConnectionString
    extraEnv: [
      { name: 'API_HOST', value: apiApp.outputs.fqdn }
    ]
    minReplicas: 1
    maxReplicas: 5
    concurrentRequests: 50
    exists: frontendExists
    image: frontendImage
  }
}

// ---------- Outputs (consumed by azd + sync_agent.py) ----------
output AZURE_LOCATION string = location
output AZURE_RESOURCE_GROUP string = resourceGroup().name
output AZURE_CONTAINER_REGISTRY_NAME string = acr.outputs.name
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = acr.outputs.loginServer
output AZURE_AI_PROJECT_ENDPOINT string = foundry.outputs.projectEndpoint
output AZURE_AI_PROJECT_NAME string = foundry.outputs.projectName
output AZURE_AI_MODEL_DEPLOYMENT string = modelName
output AZURE_FOUNDRY_AGENT_NAME string = 'clinical-trial-matcher'
output AZURE_FOUNDRY_TOOLS_CONNECTION_NAME string = foundryConnection.outputs.connectionName
output FRONTEND_URL string = 'https://${frontendApp.outputs.fqdn}'
output API_INTERNAL_FQDN string = apiApp.outputs.fqdn
output TOOLS_INTERNAL_FQDN string = toolsApp.outputs.fqdn
output TOOLS_OPENAPI_URL string = 'https://${toolsApp.outputs.fqdn}/openapi.json'
output AZURE_CLIENT_ID string = identity.outputs.clientId
