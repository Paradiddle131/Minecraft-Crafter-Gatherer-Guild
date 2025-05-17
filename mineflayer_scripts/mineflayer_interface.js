const mineflayer = require('mineflayer');
const { pathfinder, Movements } = require('mineflayer-pathfinder');

let bot = null;
let mcData = null;

function initializeBot(options) {
  return new Promise((resolve, reject) => {
    if (bot) {
      console.log('Mineflayer Bot already initialized.');
      resolve({ status: "already_initialized", username: bot.username });
      return;
    }
    try {
      bot = mineflayer.createBot(options);
      bot.loadPlugin(pathfinder);
      
      bot.once('login', () => {
        mcData = require('minecraft-data')(bot.version);
      });

      bot.once('spawn', () => {
        console.log(`Mineflayer Bot '${bot.username}' spawned in ADK project.`);
        resolve({ status: "success", username: bot.username, message: "Mineflayer bot initialized and spawned." });
      });

      bot.on('error', (err) => {
        console.error('Mineflayer Bot Error:', err);
        // If bot is not yet initialized, reject the promise.
        // If it's an error after spawn, it will just be logged.
        if (!bot.username) { // A way to check if spawn hasn't occurred
            reject({ status: "error", message: `Mineflayer Bot Error before spawn: ${err.message}` });
        }
      });

      bot.on('kicked', (reason) => {
        console.log('Mineflayer Bot Kicked:', reason);
        // If bot is not yet initialized, reject the promise.
        if (!bot.username) {
             reject({ status: "error", message: `Mineflayer Bot Kicked before spawn: ${reason}` });
        }
      });

    } catch (error) {
      console.error('Failed to initialize Mineflayer bot (catch block):', error);
      reject({ status: "error", message: error.message });
    }
  });
}

async function goToXYZ(x, y, z) {
  if (!bot || !bot.pathfinder) return { status: "error", message: "Bot not initialized or pathfinder not loaded." };
  const defaultMove = new Movements(bot, mcData);
  bot.pathfinder.setMovements(defaultMove);
  bot.pathfinder.setGoal(new pathfinder.goals.GoalBlock(x, y, z));
  return { status: "navigation_started" }; // Pathfinding is async, completion needs event handling or polling in JS if required by Python.
}

async function findBlock(blockTypeName, maxDistance = 32, count = 1) {
  if (!bot || !bot.registry) return { status: "error", message: "Bot not initialized or registry not available." };
  const block = bot.findBlock({
    matching: bot.registry.blocksByName[blockTypeName]?.id,
    maxDistance: maxDistance,
    count: count
  });
  if (block) {
    return { status: "success", location: { x: block.position.x, y: block.position.y, z: block.position.z } };
  }
  return { status: "error", message: `${blockTypeName} not found within ${maxDistance} blocks.` };
}

async function mineBlock(blockTypeName, x, y, z) {
  if (!bot) return { status: "error", message: "Bot not initialized." };
  const targetBlock = bot.blockAt(new bot.registry.Vec3(x, y, z));
  if (!targetBlock || targetBlock.name !== blockTypeName) {
    return { status: "error", message: `Block at ${x},${y},${z} is not ${blockTypeName}. It is ${targetBlock?.name}` };
  }
  if (!bot.canDigBlock(targetBlock)) {
    return { status: "error", message: `Cannot dig ${blockTypeName} at ${x},${y},${z}. Might need a better tool.` };
  }
  try {
    await bot.dig(targetBlock);
    return { status: "success", collected_item: blockTypeName }; // Simplified, real collection is event-driven
  } catch (err) {
    return { status: "error", message: `Mining failed: ${err.message}` };
  }
}

function getInventory() {
    if (!bot || !bot.inventory) return { status: "error", message: "Bot not initialized or inventory not available." };
    const items = bot.inventory.items().map(item => ({ name: item.name, count: item.count, type: item.type }));
    return { status: "success", inventory: items };
}

async function craftItem(itemName, quantity, recipeShape, ingredients, craftingTableNeeded) {
    if (!bot || !mcData) return { status: "error", message: "Bot not initialized or mcData not available." };

    const item = mcData.itemsByName[itemName];
    if (!item) return { status: "error", message: `Unknown item: ${itemName}` };

    const recipes = bot.recipesFor(item.id, null, 1, craftingTableNeeded ? bot.findBlock({ matching: mcData.blocksByName.crafting_table.id }) : null);
    if (!recipes || recipes.length === 0) {
        return { status: "error", message: `No recipe found for ${itemName}` + (craftingTableNeeded ? " with a crafting table." : ".") };
    }

    const recipeToUse = recipes;

    try {
        await bot.craft(recipeToUse, quantity, craftingTableNeeded ? bot.findBlock({ matching: mcData.blocksByName.crafting_table.id }) : null);
        return { status: "success", crafted_item: itemName, quantity_crafted: quantity };
    } catch (err) {
        return { status: "error", message: `Crafting failed: ${err.message}` };
    }
}

async function placeBlock(itemName, x, y, z, refBlockX, refBlockY, refBlockZ, faceVectorX, faceVectorY, faceVectorZ) {
    if (!bot || !mcData) return { status: "error", message: "Bot not initialized or mcData not available." };

    const itemToPlace = bot.inventory.items().find(item => item.name === itemName);
    if (!itemToPlace) {
        return { status: "error", message: `Item ${itemName} not in inventory.` };
    }

    const referenceBlock = bot.blockAt(new bot.registry.Vec3(refBlockX, refBlockY, refBlockZ));
    if (!referenceBlock) {
        return { status: "error", message: "Reference block not found." };
    }
    const faceVec = new bot.registry.Vec3(faceVectorX, faceVectorY, faceVectorZ);

    try {
        await bot.equip(itemToPlace, 'hand'); // Equip the item first
        await bot.placeBlock(referenceBlock, faceVec);
        return { status: "success", message: `Placed ${itemName} at relative location.` };
    } catch (err) {
        return { status: "error", message: `Placing block failed: ${err.message}` };
    }
}

module.exports = {
  initializeBot,
  goToXYZ,
  findBlock,
  mineBlock,
  getInventory,
  craftItem,
  placeBlock
};