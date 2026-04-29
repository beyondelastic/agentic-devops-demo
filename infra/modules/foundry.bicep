param accountName string
param projectName string
param location string
param tags object
param modelName string
param modelVersion string
param modelCapacity int
@description('Principal id of the MI that needs Azure AI User on the project.')
param principalId string

// Azure AI Foundry account (AIServices kind, supports projects + Agent Service).
resource account 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' = {
  name: accountName
  location: location
  tags: tags
  kind: 'AIServices'
  sku: { name: 'S0' }
  identity: { type: 'SystemAssigned' }
  properties: {
    customSubDomainName: accountName
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: false
    allowProjectManagement: true
  }
}

// Foundry project (child of the account).
resource project 'Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview' = {
  parent: account
  name: projectName
  location: location
  tags: tags
  identity: { type: 'SystemAssigned' }
  properties: {}
}

// Model deployment (gpt-4o-mini etc.).
resource modelDeployment 'Microsoft.CognitiveServices/accounts/deployments@2025-04-01-preview' = {
  parent: account
  name: modelName
  sku: {
    name: 'GlobalStandard'
    capacity: modelCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: modelName
      version: modelVersion
    }
    versionUpgradeOption: 'OnceNewDefaultVersionAvailable'
  }
}

// Role assignments: the user-assigned MI needs to call the Foundry project.
// "Azure AI User" — runtime use of agents and models.
var azureAIUserRoleId = '53ca6127-db72-4b80-b1b0-d745d6d5456d'
// "Cognitive Services User" — needed to invoke the underlying account.
var cognitiveUserRoleId = 'a97b65f3-24c7-4388-baec-2e87135dc908'

resource raiAIUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(project.id, principalId, azureAIUserRoleId)
  scope: project
  properties: {
    principalId: principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      azureAIUserRoleId
    )
  }
}

resource raiCognitive 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(account.id, principalId, cognitiveUserRoleId)
  scope: account
  properties: {
    principalId: principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      cognitiveUserRoleId
    )
  }
}

output accountName string = account.name
output projectName string = project.name
output projectEndpoint string = 'https://${account.properties.customSubDomainName}.services.ai.azure.com/api/projects/${project.name}'
output modelDeploymentName string = modelDeployment.name
