const mineflayer = require('mineflayer');
const mineflayerPathfinder = require('mineflayer-pathfinder');

let bot = null;
let mcData = null;

async function initializeBot(options) {
  if (bot && bot.username && bot.entity) {
    console.log('Mineflayer Bot already initialized and spawned.');
    return { status: "already_initialized", username: bot.username };
  }

  if (bot) {
    console.log('Cleaning up existing bot instance before re-initialization.');
    try {
      bot.quit('Re-initializing');
    } catch (e) {
      console.warn('Error quitting existing bot instance:', e.message);
    }
    bot = null;
    mcData = null;
  }

  console.log('Creating new Mineflayer bot instance with options:', options);
  bot = mineflayer.createBot(options);
  bot.loadPlugin(mineflayerPathfinder.pathfinder);

  try {
    await new Promise((resolve, reject) => {
      let spawned = false;
      
      const listeners = {
        loginListener: () => {
          try {
            mcData = require('minecraft-data')(bot.version);
            console.log(`Mineflayer Bot logged in. mcData version: ${bot.version}. Username: ${bot.username}`);
          } catch (mcDataError) {
            console.error('Failed to load minecraft-data:', mcDataError);
            if (!spawned) reject(new Error(`Failed to load minecraft-data: ${mcDataError.message}`));
          }
        },
        spawnListener: () => {
          spawned = true;
          console.log(`Mineflayer Bot '${bot.username}' spawned in ADK project.`);
          bot.removeListener('error', listeners.errorListener);
          bot.removeListener('kicked', listeners.kickListener);
          bot.removeListener('login', listeners.loginListener);
          
          bot.on('error', (err) => console.error('Mineflayer Bot Error (post-spawn):', err));
          bot.on('kicked', (reason) => console.log('Mineflayer Bot Kicked (post-spawn):', reason));
          
          resolve();

          // Optional initial teleport
          if (options.initial_teleport_coords &&
              Array.isArray(options.initial_teleport_coords) &&
              options.initial_teleport_coords.length === 3 &&
              options.initial_teleport_coords.every(coord => typeof coord === 'number')) {
            
            const [tpX, tpY, tpZ] = options.initial_teleport_coords;
            console.log(`Teleporting the bot '${bot.username}' to ${tpX} ${tpY} ${tpZ}`);
            bot.chat(`/tp ${bot.username} ${tpX} ${tpY} ${tpZ}`);
          }
        },
        errorListener: (err) => {
          if (!spawned) {
            console.error('Mineflayer Bot Error (pre-spawn):', err);
            bot.removeListener('login', listeners.loginListener);
            bot.removeListener('spawn', listeners.spawnListener);
            bot.removeListener('kicked', listeners.kickListener);
            reject(err);
          }
        },
        kickListener: (reason) => {
          if (!spawned) {
            console.log('Mineflayer Bot Kicked (pre-spawn):', reason);
            bot.removeListener('login', listeners.loginListener);
            bot.removeListener('spawn', listeners.spawnListener);
            bot.removeListener('error', listeners.errorListener);
            reject(new Error(String(reason)));
          }
        }
      };
      
      bot.once('login', listeners.loginListener);
      bot.once('spawn', listeners.spawnListener);
      bot.once('error', listeners.errorListener);
      bot.once('kicked', listeners.kickListener);
    });

    return { status: "success", username: bot.username, message: "Mineflayer bot initialized and spawned." };

  } catch (error) {
    console.error('Failed to initialize Mineflayer bot (outer promise catch):', error);
    if (bot) {
        try { bot.quit('Initialization failed'); } catch (e) { /* ignore */ }
        bot = null;
        mcData = null;
    }
    const errorMessage = error && error.message ? error.message : "Unknown error during initialization.";
    return { status: "error", message: errorMessage };
  }
}

async function goToXYZ(x, y, z) {
  if (!bot || !bot.pathfinder) return { status: "error", message: "Bot not initialized or pathfinder not loaded." };
  const defaultMove = new mineflayerPathfinder.Movements(bot, mcData);
  bot.pathfinder.setMovements(defaultMove);
  bot.pathfinder.setGoal(new mineflayerPathfinder.goals.GoalBlock(x, y, z));
  return { status: "navigation_started" }; // Pathfinding is async, completion needs event handling or polling in JS if required by Python.
}

function findBlock(blockTypeName, maxDistance = 32, count = 1) {
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